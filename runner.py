#!/usr/bin/env python3
import os
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path

from app.db import get_db

_REPORT_FILES = [
    "executive-report.html",
    "compliance-nis2.html",
    "compliance-nis2.pdf",
    "security-report.json",
    "debt-report.json",
]

PROJECT_DIR = Path(__file__).parent
MAX_CONCURRENT = int(os.getenv("RUNNER_CONCURRENCY", "3"))
SLEEP_INTERVAL = int(os.getenv("RUNNER_INTERVAL", "30"))

_semaphore = threading.Semaphore(MAX_CONCURRENT)
_lock = threading.Lock()

TASK_STATUSES = ("pending", "running", "done", "failed")


def add_task(
    repo_url: str,
    customer_email: str = "",
    plan_type: str = "auditoria_unica",
    user_id: int = 0,
    demo_id: str = "",
) -> dict:
    db = get_db()
    audit_dir = f"/tmp/audit-{uuid.uuid4()}"
    db.execute(
        """INSERT INTO tasks (user_id, repo_url, customer_email, plan_type, status, audit_dir, demo_id)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (user_id, repo_url, customer_email, plan_type, "pending", audit_dir, demo_id),
    )
    db.commit()
    task_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    db.close()
    print(f"✓ Tarea #{task_id} añadida: {repo_url}")
    return {"id": task_id, "repo_url": repo_url, "status": "pending", "audit_dir": audit_dir}


def get_pending_tasks() -> list[dict]:
    db = get_db()
    rows = db.execute(
        "SELECT * FROM tasks WHERE status = 'pending' ORDER BY created_at ASC LIMIT ?",
        (MAX_CONCURRENT,),
    ).fetchall()
    db.close()
    return [dict(r) for r in rows]


def update_task(task_id: int, status: str, error: str = ""):
    db = get_db()
    if status == "running":
        db.execute(
            "UPDATE tasks SET status = ?, started_at = datetime('now') WHERE id = ?",
            (status, task_id),
        )
    elif status in ("done", "failed"):
        db.execute(
            "UPDATE tasks SET status = ?, finished_at = datetime('now'), error = ? WHERE id = ?",
            (status, error, task_id),
        )
    else:
        db.execute("UPDATE tasks SET status = ? WHERE id = ?", (status, task_id))
    db.commit()
    db.close()


def _get_compliance_score() -> int | None:
    import re
    html_path = PROJECT_DIR / "reports" / "compliance-nis2.html"
    if not html_path.exists():
        return None
    m = re.search(r"overall[-_ ]?score[^>]*>\s*(\d+)", html_path.read_text(encoding="utf-8"), re.IGNORECASE)
    return int(m.group(1)) if m else None


def _trigger_integrations(repo_url: str, task_id: int):
    siem_webhook = os.getenv("SIEM_WEBHOOK_URL", "")
    jira_url = os.getenv("JIRA_URL", "")
    jira_email = os.getenv("JIRA_EMAIL", "")
    jira_token = os.getenv("JIRA_API_TOKEN", "")

    if not siem_webhook and not (jira_url and jira_email and jira_token):
        return

    score = _get_compliance_score()
    if score is not None and score >= 70:
        print(f"  ℹ️  Score {score}/100 >= 70 — integraciones no requeridas")
        return

    sec_path = PROJECT_DIR / "reports" / "security-report.json"
    if not sec_path.exists():
        return

    try:
        sec_data = json.loads(sec_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return

    secrets = sec_data.get("secrets", [])
    vuln_deps = sec_data.get("vulnerable_dependencies", [])
    critical = [v for v in vuln_deps if v.get("severity", "").upper() in ("CRITICAL", "HIGH")]

    if not secrets and not critical:
        print(f"  ℹ️  Sin hallazgos críticos — integraciones no requeridas")
        return

    # ── SIEM ─────────────────────────────────────────────────────────
    if siem_webhook:
        try:
            sys.path.insert(0, str(PROJECT_DIR))
            from integrations.siem import send_batch
            hallazgos = []
            for s in secrets:
                hallazgos.append({
                    "type": "secret",
                    "severity": "CRITICAL",
                    "file": s.get("file", ""),
                    "line": s.get("line", 0),
                    "reason": s.get("reason", "Secreto detectado"),
                    "repo_url": repo_url,
                })
            for d in critical:
                hallazgos.append({
                    "type": "vulnerable_dependency",
                    "severity": d.get("severity", "HIGH"),
                    "file": d.get("file", ""),
                    "line": d.get("line", 0),
                    "reason": f"{d.get('name', '?')} - {d.get('title', '')}",
                    "repo_url": repo_url,
                })
            ok, fail = send_batch(hallazgos)
            print(f"  📡 SIEM: {ok} enviados, {fail} fallos")
        except Exception as e:
            print(f"  ⚠️  Error integración SIEM: {e}")

    # ── Jira ──────────────────────────────────────────────────────────
    if jira_url and jira_email and jira_token:
        try:
            sys.path.insert(0, str(PROJECT_DIR))
            from integrations.jira import sync_findings
            tickets = sync_findings()
            if tickets:
                print(f"  🎫 Jira: {len(tickets)} ticket(s) creados")
        except Exception as e:
            print(f"  ⚠️  Error integración Jira: {e}")


def _register_reports(task_id: int, user_id: int, repo_url: str):
    try:
        db = get_db()
        for fname in _REPORT_FILES:
            if (PROJECT_DIR / "reports" / fname).exists():
                existing = db.execute(
                    "SELECT id FROM report_registry WHERE task_id = ? AND filename = ?",
                    (task_id, fname),
                ).fetchone()
                if not existing:
                    db.execute(
                        "INSERT INTO report_registry (task_id, user_id, filename, repo_url) VALUES (?, ?, ?, ?)",
                        (task_id, user_id, fname, repo_url),
                    )
        db.commit()
        db.close()
    except Exception as e:
        print(f"  ⚠️ Error registrando reportes: {e}")


def process_task(task: dict) -> bool:
    task_id = task["id"]
    repo_url = task["repo_url"]
    audit_dir = task.get("audit_dir", f"/tmp/audit-{uuid.uuid4()}")

    update_task(task_id, "running")

    print(f"\n{'='*60}")
    print(f"  Ejecutando tarea #{task_id}: {repo_url}")
    print(f"  Audit dir: {audit_dir}")
    print(f"{'='*60}")

    # Clonar repo si es URL
    is_remote = repo_url.startswith("http") or repo_url.startswith("git@")
    target_path = audit_dir if is_remote else repo_url

    if is_remote:
        clone_cmd = ["git", "clone", "--depth", "1", repo_url, audit_dir]
        clone_result = subprocess.run(clone_cmd, capture_output=True, text=True, timeout=120)
        if clone_result.returncode != 0:
            print(f"  ❌ Error al clonar: {clone_result.stderr[:300]}")
            update_task(task_id, "failed", clone_result.stderr[:500])
            return False

    result = subprocess.run(
        [sys.executable, "engine/run.py", target_path, "--audit-id", str(task_id)],
        capture_output=True, text=True, timeout=600,
        cwd=str(PROJECT_DIR),
    )

    if result.returncode != 0:
        print(f"  ❌ Falló la auditoría (código {result.returncode})")
        print(f"  Error: {result.stderr[:500]}")
        update_task(task_id, "failed", result.stderr[:500])
        return False

    print(f"  ✓ Auditoría completada")

    report_path = PROJECT_DIR / "reports" / "executive-report.html"
    compliance_html = PROJECT_DIR / "reports" / "compliance-nis2.html"
    compliance_pdf = PROJECT_DIR / "reports" / "compliance-nis2.pdf"

    # Generate compliance report
    print("  📋 Generando informe de cumplimiento normativo...")
    subprocess.run(
        [sys.executable, str(PROJECT_DIR / "compliance_report.py")],
        cwd=str(PROJECT_DIR), capture_output=True, timeout=120,
    )

    if compliance_pdf.exists():
        print(f"  ✓ Compliance PDF generado")

    # Certify report with SHA-256 + QR
    try:
        subprocess.run(
            [sys.executable, str(PROJECT_DIR / "certify.py"), "--certify"],
            cwd=str(PROJECT_DIR), capture_output=True, timeout=60,
        )
        print("  🔏 Informe certificado con SHA-256 + QR")
    except Exception as e:
        print(f"  ⚠️ Error en certificación: {e}")

    # Register reports for multi-tenant access control
    _register_reports(task_id, task.get("user_id", 0), repo_url)

    # Fire async SIEM/Jira integrations
    threading.Thread(
        target=_trigger_integrations,
        args=(repo_url, task_id),
        daemon=True,
    ).start()

    # Send email
    email_script = PROJECT_DIR / "email_sender.py"
    if email_script.exists() and task.get("customer_email"):
        customer_email = task["customer_email"]
        dashboard_token = f"dash_{os.urandom(8).hex()}"
        domain = os.getenv("DOMAIN", "http://localhost:5001")
        dashboard_url = f"{domain}/dashboard?token={dashboard_token}&uid={task.get('user_id', 0)}"

        sales_body_html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="font-family:Arial,sans-serif;padding:20px;background:#f4f4f4;">
<div style="max-width:600px;margin:0 auto;background:white;border-radius:12px;padding:30px;">
    <h2 style="color:#6366f1;">📄 CodeAudit Pro — Informe de Auditoría</h2>
    <p>Estimado cliente,</p>
    <p>Adjuntamos el informe de auditoría de seguridad y cumplimiento normativo de <strong>{repo_url}</strong>.</p>

    <h3 style="color:#1e293b;">Informe ejecutivo</h3>
    <p>Puedes consultar los resultados detallados en tu panel privado.</p>

    <div style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:8px;padding:16px;margin:20px 0;">
        <h3 style="color:#16a34a;margin-top:0;">🔑 Acceso al panel de control</h3>
        <p><strong>Email:</strong> {customer_email}</p>
        <p style="text-align:center;margin:16px 0;">
            <a href="{dashboard_url}" style="display:inline-block;background:#16a34a;color:white;padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:bold;">Acceder al Dashboard</a>
        </p>
    </div>

    <p style="margin-top:30px;color:#94a3b8;font-size:12px;">
        CodeAudit Pro · Cumplimiento NIS2 · DORA · GDPR<br>
        {domain}
    </p>
</div></body></html>"""

        body_file = PROJECT_DIR / "reports" / "_delivery_email.html"
        body_file.write_text(sales_body_html, encoding="utf-8")

        attachments = []
        if compliance_pdf.exists():
            attachments.extend(["--attach", str(compliance_pdf)])
        if report_path.exists():
            attachments.extend(["--attach", str(report_path)])

        cmd = [
            sys.executable, str(email_script),
            "--to", customer_email,
            "--subject", f"CodeAudit Pro — Informe de seguridad y cumplimiento ({repo_url})",
            "--body", str(body_file),
        ] + attachments
        subprocess.run(cmd, cwd=str(PROJECT_DIR))

    # Clean up cloned repo
    if is_remote:
        subprocess.run(["rm", "-rf", audit_dir])

    update_task(task_id, "done")
    return True


def process_pending_tasks():
    if _semaphore.acquire(blocking=False):
        try:
            tasks = get_pending_tasks()
            if not tasks:
                return
            print(f"\n📋 {len(tasks)} tarea(s) pendiente(s) en cola (máx {MAX_CONCURRENT} concurrentes)")
            threads = []
            for task in tasks:
                t = threading.Thread(target=process_task, args=(task,))
                t.start()
                threads.append(t)
            for t in threads:
                t.join()
        finally:
            _semaphore.release()
    else:
        print(f"  ⏳ Semáforo ocupado ({MAX_CONCURRENT} procesos ya activos)")


def list_tasks(status: str | None = None):
    db = get_db()
    if status:
        rows = db.execute(
            "SELECT * FROM tasks WHERE status = ? ORDER BY created_at DESC", (status,)
        ).fetchall()
    else:
        rows = db.execute("SELECT * FROM tasks ORDER BY created_at DESC").fetchall()
    db.close()

    print(f"\n{'='*70}")
    print(f"  TAREAS ({len(rows)})")
    print(f"{'='*70}")
    if not rows:
        print("  (no hay tareas)")
        return

    for r in rows:
        t = dict(r)
        icon = {"pending": "⏳", "running": "🔄", "done": "✅", "failed": "❌"}.get(t["status"], "❓")
        print(f"\n  {icon} #{t['id']} - {t['repo_url']}")
        print(f"     Cliente: {t.get('customer_email', '-')}")
        print(f"     Plan:    {t.get('plan_type', '-')}")
        print(f"     Estado:  {t['status']}")
        print(f"     Dir:     {t.get('audit_dir', '-')}")
        if t.get("finished_at"):
            print(f"     Fin:     {t['finished_at']}")
        if t.get("error"):
            print(f"     Error:   {t['error']}")


def _migrate_from_json():
    json_path = PROJECT_DIR / "data" / "tasks.json"
    if not json_path.exists():
        return
    try:
        import json as _json
        old_tasks = _json.loads(json_path.read_text(encoding="utf-8"))
    except Exception:
        return
    if not old_tasks:
        return
    db = get_db()
    existing = db.execute("SELECT COUNT(*) as c FROM tasks").fetchone()["c"]
    if existing > 0:
        print(f"  ↪ La DB ya tiene {existing} tareas. Omitiendo migración.")
        db.close()
        return
    for t in old_tasks:
        db.execute(
            """INSERT INTO tasks (id, user_id, repo_url, customer_email, plan_type, status, created_at, completed_at, error)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                t.get("id"),
                t.get("user_id", 0),
                t.get("repo_url", ""),
                t.get("customer_email", ""),
                t.get("plan_type", "auditoria_unica"),
                t.get("status", "pending"),
                t.get("created_at", datetime.now().isoformat()),
                t.get("completed_at"),
                t.get("error", ""),
            ),
        )
    db.commit()
    db.close()
    print(f"  ↪ Migradas {len(old_tasks)} tareas desde tasks.json")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Runner con cola SQLite y concurrencia")
    parser.add_argument("--add", help="Añadir tarea: repo_url")
    parser.add_argument("--email", help="Email del cliente (con --add)")
    parser.add_argument("--plan", default="auditoria_unica", help="Plan")
    parser.add_argument("--user-id", type=int, default=0, help="ID de usuario")
    parser.add_argument("--demo-id", default="", help="ID de demo gratuita")
    parser.add_argument("--run-once", action="store_true", help="Procesar tareas y salir")
    parser.add_argument("--daemon", action="store_true", help="Ejecutar en bucle")
    parser.add_argument("--list", nargs="?", const="", help="Listar tareas")
    parser.add_argument("--migrate", action="store_true", help="Migrar desde tasks.json")

    args = parser.parse_args()

    if args.migrate:
        _migrate_from_json()
        return

    if args.add:
        add_task(args.add, args.email or "", args.plan, args.user_id, args.demo_id)

    if args.run_once:
        process_pending_tasks()

    elif args.daemon:
        print(f"🧠 Daemon iniciado (intervalo: {SLEEP_INTERVAL}s, concurrencia: {MAX_CONCURRENT})")
        print("   Presiona Ctrl+C para detener")
        try:
            while True:
                process_pending_tasks()
                time.sleep(SLEEP_INTERVAL)
        except KeyboardInterrupt:
            print("\nDaemon detenido.")

    if args.list is not None:
        list_tasks(args.list if args.list else None)

    if not any(vars(args).values()):
        parser.print_help()


if __name__ == "__main__":
    main()

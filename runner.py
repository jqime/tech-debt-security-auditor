#!/usr/bin/env python3
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

PROJECT_DIR = Path(__file__).parent
DATA_DIR = PROJECT_DIR / "data"
TASKS_FILE = DATA_DIR / "tasks.json"
SLEEP_INTERVAL = int(os.getenv("RUNNER_INTERVAL", "30"))


def ensure_tasks_file():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not TASKS_FILE.exists():
        TASKS_FILE.write_text("[]", encoding="utf-8")


def load_tasks() -> list[dict]:
    ensure_tasks_file()
    try:
        return json.loads(TASKS_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []


def save_tasks(tasks: list[dict]):
    TASKS_FILE.write_text(json.dumps(tasks, indent=2, ensure_ascii=False), encoding="utf-8")


def add_task(repo_url: str, customer_email: str, plan_type: str = "auditoria_unica", user_id: int = 0) -> dict:
    ensure_tasks_file()
    tasks = load_tasks()
    task = {
        "id": len(tasks) + 1,
        "user_id": user_id,
        "repo_url": repo_url,
        "customer_email": customer_email,
        "plan_type": plan_type,
        "status": "pending",
        "created_at": datetime.now().isoformat(),
        "completed_at": None,
    }
    tasks.append(task)
    save_tasks(tasks)
    print(f"✓ Tarea #{task['id']} añadida: {repo_url}")
    return task


def process_task(task: dict) -> bool:
    print(f"\n{'='*60}")
    print(f"  Ejecutando tarea #{task['id']}: {task['repo_url']}")
    print(f"  Cliente: {task['customer_email']}")
    print(f"{'='*60}")

    result = subprocess.run(
        ["./run_audit.sh", task["repo_url"]],
        capture_output=True, text=True, timeout=600,
        cwd=str(PROJECT_DIR),
    )

    if result.returncode != 0:
        print(f"  ❌ Falló la auditoría (código {result.returncode})")
        print(f"  Error: {result.stderr[:500]}")
        return False

    print(f"  ✓ Auditoría completada")

    report_path = PROJECT_DIR / "reports" / "executive-report.html"
    compliance_html = PROJECT_DIR / "reports" / "compliance-nis2.html"
    compliance_pdf = PROJECT_DIR / "reports" / "compliance-nis2.pdf"

    # Generate compliance report
    print("  📋 Generando informe de cumplimiento normativo...")
    subprocess.run(
        [sys.executable, str(PROJECT_DIR / "compliance_report.py")],
        cwd=str(PROJECT_DIR),
        capture_output=True, timeout=120,
    )

    if compliance_pdf.exists():
        print(f"  ✓ Compliance PDF generado ({compliance_pdf})")

    # Send sales email with compliance demo
    email_script = PROJECT_DIR / "email_sender.py"
    if email_script.exists():
        is_free_plan = task.get("plan_type") in ("gratuito", "auditoria_unica") or not task.get("plan_type")
        plan_label = "GRATUITO" if is_free_plan else task.get("plan_type", "auditoria_unica")

        compliance_score = ""
        try:
            if compliance_html.exists():
                import re
                m = re.search(r'overall-score[^>]*>(\d+)', compliance_html.read_text(encoding="utf-8"))
                if m:
                    compliance_score = m.group(1)
        except Exception:
            pass

        sales_body_html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="font-family:Arial,sans-serif;padding:20px;background:#f4f4f4;">
<div style="max-width:600px;margin:0 auto;background:white;border-radius:12px;padding:30px;">
    <h2 style="color:#6366f1;">🛡️ CodeAudit Pro — Informe de Auditoría</h2>
    <p>Estimado cliente,</p>
    <p>Adjuntamos el informe de auditoría de seguridad y cumplimiento normativo de <strong>{task['repo_url']}</strong>.</p>
    <p><strong>Plan utilizado:</strong> {plan_label}</p>
    {f'<p><strong>Score de cumplimiento NIS2/DORA:</strong> {compliance_score}/100</p>' if compliance_score else ''}

    <div style="background:#f0f0ff;border-radius:8px;padding:20px;margin:20px 0;">
        <h3 style="color:#4338ca;margin-top:0;">📋 ¿Necesitas cumplir con NIS2 o DORA?</h3>
        <p>Con <strong>CodeAudit Pro Compliance</strong> obtienes:</p>
        <table style="width:100%;border-collapse:collapse;">
            <tr style="border-bottom:1px solid #ddd;"><td style="padding:8px 0;">✅ Informe completo NIS2 + DORA</td></tr>
            <tr style="border-bottom:1px solid #ddd;"><td style="padding:8px 0;">✅ Certificación blockchain (hash + QR)</td></tr>
            <tr style="border-bottom:1px solid #ddd;"><td style="padding:8px 0;">✅ Declaración de debida diligencia para auditores</td></tr>
            <tr style="border-bottom:1px solid #ddd;"><td style="padding:8px 0;">✅ PDF descargable</td></tr>
            <tr><td style="padding:8px 0;">✅ Integración con Jira para remediation</td></tr>
        </table>
        <p style="margin-top:15px;text-align:center;">
            <a href="/try-now" style="display:inline-block;background:#6366f1;color:white;padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:bold;">Probar demo gratuita</a>
        </p>
        <table style="width:100%;margin-top:15px;border-collapse:collapse;font-size:12px;">
            <tr style="border-bottom:1px solid #ddd;"><td style="padding:4px 8px;">Professional</td><td style="padding:4px 8px;">9.900 €/año</td><td style="padding:4px 8px;">10 repos, informes mensuales</td></tr>
            <tr style="border-bottom:1px solid #ddd;"><td style="padding:4px 8px;">Enterprise</td><td style="padding:4px 8px;">29.900 €/año</td><td style="padding:4px 8px;">50 repos, SIEM, white-label, 24/7</td></tr>
            <tr><td style="padding:4px 8px;">Custom</td><td style="padding:4px 8px;">Bajo demanda</td><td style="padding:4px 8px;">On-premise, SLA dedicado</td></tr>
        </table>
        <p style="text-align:center;margin:5px 0 0;font-size:12px;color:#94a3b8;"><a href="/terms" style="color:#94a3b8;">Términos</a> · <a href="/privacy" style="color:#94a3b8;">Privacidad</a></p>
    </div>

    <p>Si tienes cualquier pregunta, responde a este correo.</p>
    <p style="margin-top:30px;color:#94a3b8;font-size:12px;">
        CodeAudit Pro · Auditoría de código para PYMES<br>
        Cumplimiento NIS2 · DORA · GDPR
    </p>
</div></body></html>"""

        # Save body to temp file for email_sender
        body_file = PROJECT_DIR / "reports" / "_sales_email.html"
        body_file.write_text(sales_body_html, encoding="utf-8")

        attach = str(compliance_pdf) if compliance_pdf.exists() else (str(compliance_html) if compliance_html.exists() else str(report_path))
        subprocess.run(
            [sys.executable, str(email_script),
             "--to", task["customer_email"],
             "--subject", f"CodeAudit Pro — Informe y Cumplimiento Normativo ({task['repo_url']})",
             "--body", str(body_file),
             "--attach", attach],
            cwd=str(PROJECT_DIR),
        )

    return True


def process_pending_tasks():
    tasks = load_tasks()
    pending = [t for t in tasks if t["status"] == "pending"]
    if not pending:
        return

    print(f"\n📋 {len(pending)} tarea(s) pendiente(s) en cola")
    for task in pending:
        success = process_task(task)
        task["status"] = "completed" if success else "failed"
        task["completed_at"] = datetime.now().isoformat()
        save_tasks(tasks)


def list_tasks(status: str | None = None):
    tasks = load_tasks()
    if status:
        tasks = [t for t in tasks if t["status"] == status]

    print(f"\n{'='*70}")
    print(f"  TAREAS ({len(tasks)})")
    print(f"{'='*70}")
    if not tasks:
        print("  (no hay tareas)")
        return

    for t in tasks:
        icon = {"pending": "⏳", "completed": "✅", "failed": "❌"}.get(t["status"], "❓")
        print(f"\n  {icon} #{t['id']} - {t['repo_url']}")
        print(f"     Cliente: {t['customer_email']}")
        print(f"     Plan:    {t['plan_type']}")
        print(f"     Estado:  {t['status']}")
        if t.get("completed_at"):
            print(f"     Completado: {t['completed_at']}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Automatización de cola de tareas")
    parser.add_argument("--add", help="Añadir tarea: repo_url")
    parser.add_argument("--email", help="Email del cliente (con --add)")
    parser.add_argument("--plan", default="auditoria_unica", help="Plan (auditoria_unica|suscripcion_mensual)")
    parser.add_argument("--user-id", type=int, default=0, help="ID de usuario en el dashboard")
    parser.add_argument("--run-once", action="store_true", help="Procesar tareas pendientes y salir")
    parser.add_argument("--daemon", action="store_true", help="Ejecutar en bucle como daemon")
    parser.add_argument("--list", nargs="?", const="", help="Listar tareas (opcional: pending|completed|failed)")

    args = parser.parse_args()

    if args.add:
        add_task(args.add, args.email or "cliente@ejemplo.com", args.plan, args.user_id)
    elif args.run_once:
        process_pending_tasks()
    elif args.daemon:
        print(f"🧠 Daemon iniciado (intervalo: {SLEEP_INTERVAL}s)")
        print("   Presiona Ctrl+C para detener")
        try:
            while True:
                process_pending_tasks()
                time.sleep(SLEEP_INTERVAL)
        except KeyboardInterrupt:
            print("\nDaemon detenido.")
    elif args.list is not None:
        list_tasks(args.list if args.list else None)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

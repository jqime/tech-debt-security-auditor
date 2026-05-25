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
        ["./run-audit.sh", task["repo_url"]],
        capture_output=True, text=True, timeout=600,
        cwd=str(PROJECT_DIR),
    )

    if result.returncode != 0:
        print(f"  ❌ Falló la auditoría (código {result.returncode})")
        print(f"  Error: {result.stderr[:500]}")
        return False

    print(f"  ✓ Auditoría completada")

    report_path = PROJECT_DIR / "reports" / "executive-report.html"
    if report_path.exists():
        email_script = PROJECT_DIR / "email_sender.py"
        if email_script.exists():
            subprocess.run(
                [sys.executable, str(email_script),
                 "--to", task["customer_email"],
                 "--subject", f"Informe de auditoría - {task['repo_url']}",
                 "--attach", str(report_path)],
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

#!/usr/bin/env python3
import hashlib
import hmac
import json
import os
import subprocess
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from flask import Flask, jsonify, request

PROJECT_DIR = Path(__file__).parent
DATA_DIR = PROJECT_DIR / "data" / "continuous_audits"
WEBHOOK_LOG = DATA_DIR / "webhook_log.jsonl"
SCHEDULES_FILE = DATA_DIR / "schedules.json"
HISTORY_FILE = DATA_DIR / "history.json"
PORT = int(os.getenv("CONTINUOUS_PORT", "5003"))
GITHUB_WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET", "")

try:
    from apscheduler.schedulers.background import BackgroundScheduler
    HAS_SCHEDULER = True
except ImportError:
    HAS_SCHEDULER = False

app = Flask(__name__)


def ensure_dirs():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for f in [WEBHOOK_LOG, SCHEDULES_FILE, HISTORY_FILE]:
        if not f.exists():
            f.write_text("[]" if f.suffix == ".json" else "", encoding="utf-8")


def log_webhook(event_type: str, payload: dict):
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": event_type,
        "payload": payload,
    }
    with open(WEBHOOK_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def verify_signature(payload_data: bytes, sig_256: str, sig_1: str = "") -> bool:
    if not GITHUB_WEBHOOK_SECRET:
        print("  ⚠️  GITHUB_WEBHOOK_SECRET no configurado — saltando verificación")
        return True
    if not sig_256 and not sig_1:
        print("  ❌ Firma HMAC ausente — rechazando")
        return False
    expected_256 = "sha256=" + hmac.new(
        GITHUB_WEBHOOK_SECRET.encode(), payload_data, hashlib.sha256
    ).hexdigest()
    if sig_256 and hmac.compare_digest(expected_256, sig_256):
        return True
    expected_1 = "sha1=" + hmac.new(
        GITHUB_WEBHOOK_SECRET.encode(), payload_data, hashlib.sha1
    ).hexdigest()
    if sig_1 and hmac.compare_digest(expected_1, sig_1):
        return True
    print("  ❌ Firma HMAC inválida — rechazando")
    return False


def trigger_audit(repo_url: str, email: str = "cliente@ejemplo.com"):
    subprocess.Popen(
        [sys.executable, str(PROJECT_DIR / "runner.py"), "--add", repo_url, "--email", email],
        cwd=str(PROJECT_DIR),
    )


def load_schedules():
    try:
        return json.loads(SCHEDULES_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, FileNotFoundError):
        return []


def save_schedules(schedules: list):
    SCHEDULES_FILE.write_text(json.dumps(schedules, indent=2, ensure_ascii=False), encoding="utf-8")


def load_history():
    try:
        return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, FileNotFoundError):
        return []


def save_history(history: list):
    HISTORY_FILE.write_text(json.dumps(history, indent=2, ensure_ascii=False), encoding="utf-8")


def get_compliance_score() -> int | None:
    html_path = PROJECT_DIR / "reports" / "compliance-nis2.html"
    if not html_path.exists():
        return None
    import re
    m = re.search(r"overall-score[^>]*>(\d+)", html_path.read_text(encoding="utf-8"))
    return int(m.group(1)) if m else None


def check_score_drop(repo_url: str, new_score: int):
    history = load_history()
    prev_scores = [h["score"] for h in history if h["repo"] == repo_url]
    if prev_scores and (prev_scores[-1] - new_score) > 10:
        from email_sender import send_email
        schedule = next((s for s in load_schedules() if s["repo_url"] == repo_url), None)
        if schedule:
            send_email(
                to_email=schedule["email"],
                subject="Alerta: Caída de puntuación de cumplimiento",
                html_body=(
                    f"<h2>CodeAudit Pro</h2>"
                    f"<p>La puntuación de cumplimiento para <strong>{repo_url}</strong> "
                    f"ha bajado de <strong>{prev_scores[-1]}</strong> a <strong>{new_score}</strong>.</p>"
                    f"<p>Diferencia: {prev_scores[-1] - new_score} puntos.</p>"
                ),
            )


def record_audit(repo_url: str, score: int | None = None):
    history = load_history()
    entry = {
        "repo": repo_url,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "score": score,
    }
    history.append(entry)
    save_history(history)
    if score is not None:
        check_score_drop(repo_url, score)


# ---------------------------------------------------------------------------
#  Webhook
# ---------------------------------------------------------------------------

@app.route("/webhook/github", methods=["POST"])
def webhook_github():
    payload_data = request.get_data()
    sig_256 = request.headers.get("X-Hub-Signature-256", "")
    sig_1 = request.headers.get("X-Hub-Signature", "")
    if not verify_signature(payload_data, sig_256, sig_1):
        return jsonify({"error": "Firma HMAC inválida"}), 401

    event = request.headers.get("X-GitHub-Event", "unknown")
    payload = request.get_json(silent=True) or {}

    log_webhook(event, payload)

    if event == "push":
        repo_url = payload.get("repository", {}).get("clone_url", "")
        if repo_url:
            trigger_audit(repo_url)

    elif event == "pull_request":
        pr = payload.get("pull_request", {})
        head = pr.get("head", {})
        repo = head.get("repo", {}) or payload.get("repository", {})
        repo_url = repo.get("clone_url", "")
        if repo_url:
            trigger_audit(repo_url)

    return jsonify({"status": "recibido"}), 200


# ---------------------------------------------------------------------------
#  Schedule management
# ---------------------------------------------------------------------------

@app.route("/schedule/add", methods=["GET"])
def schedule_add():
    repo_url = request.args.get("repo_url", "")
    interval = request.args.get("interval", "daily")
    email = request.args.get("email", "")

    if not repo_url:
        return jsonify({"error": "Falta parámetro repo_url"}), 400

    schedules = load_schedules()
    new_id = max([s["id"] for s in schedules], default=0) + 1
    schedule = {
        "id": new_id,
        "repo_url": repo_url,
        "interval": interval,
        "email": email,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "last_run": None,
    }
    schedules.append(schedule)
    save_schedules(schedules)
    return jsonify({"status": "ok", "schedule": schedule})


@app.route("/schedule/remove", methods=["GET"])
def schedule_remove():
    sid = request.args.get("id", "")
    if not sid:
        return jsonify({"error": "Falta parámetro id"}), 400
    schedules = load_schedules()
    schedules = [s for s in schedules if s["id"] != int(sid)]
    save_schedules(schedules)
    return jsonify({"status": "eliminado"})


@app.route("/schedule/list", methods=["GET"])
def schedule_list():
    return jsonify(load_schedules())


# ---------------------------------------------------------------------------
#  Dashboard
# ---------------------------------------------------------------------------

@app.route("/status", methods=["GET"])
def status():
    tasks_file = PROJECT_DIR / "data" / "tasks.json"
    try:
        tasks = json.loads(tasks_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, FileNotFoundError):
        tasks = []

    running = sum(1 for t in tasks if t.get("status") == "running")
    pending = sum(1 for t in tasks if t.get("status") == "pending")
    scheduled = len(load_schedules())

    return jsonify({
        "tareas_ejecutandose": running,
        "tareas_pendientes": pending,
        "programaciones": scheduled,
    })


@app.route("/history", methods=["GET"])
def history():
    repo = request.args.get("repo", "")
    history_data = load_history()
    if repo:
        history_data = [h for h in history_data if repo in h["repo"]]
    return jsonify(history_data)


# ---------------------------------------------------------------------------
#  Scheduler background job
# ---------------------------------------------------------------------------

def run_due_schedules():
    if not HAS_SCHEDULER:
        return
    schedules = load_schedules()
    now = datetime.now(timezone.utc)
    for s in schedules:
        run = False
        if s["last_run"] is None:
            run = True
        else:
            last = datetime.fromisoformat(s["last_run"])
            delta_hours = (now - last).total_seconds() / 3600
            if s["interval"] == "daily" and delta_hours >= 24:
                run = True
            elif s["interval"] == "weekly" and delta_hours >= 168:
                run = True
        if run:
            trigger_audit(s["repo_url"], s.get("email", ""))
            s["last_run"] = now.isoformat()
    save_schedules(schedules)


def start_scheduler():
    if not HAS_SCHEDULER:
        print("  ⚠️  APScheduler no instalado. Las programaciones automáticas están desactivadas.")
        print("     Instala con: pip install apscheduler")
        return None
    scheduler = BackgroundScheduler()
    scheduler.add_job(run_due_schedules, "interval", hours=1, id="check_schedules")
    scheduler.start()
    print("  📅 Programador automático iniciado (revisión cada 1 hora)")
    return scheduler


# ---------------------------------------------------------------------------
#  CLI
# ---------------------------------------------------------------------------

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Servicio de auditoría continua")
    parser.add_argument("--daemon", action="store_true", help="Iniciar servidor webhook + programador")
    args = parser.parse_args()

    ensure_dirs()

    if args.daemon:
        print("=" * 60)
        print("  🛡️  CodeAudit Pro — Servicio de Auditoría Continua")
        print("=" * 60)
        scheduler = start_scheduler()
        print(f"  🌐 Servidor webhook en puerto {PORT}")
        print("  Presiona Ctrl+C para detener")
        try:
            app.run(host="0.0.0.0", port=PORT, debug=False)
        except KeyboardInterrupt:
            print("\nServicio detenido.")
        finally:
            if scheduler:
                scheduler.shutdown()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

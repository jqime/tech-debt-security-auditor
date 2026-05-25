#!/usr/bin/env python3
import csv
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, request
from flask_cors import CORS

PROJECT_DIR = Path(__file__).parent
DATA_DIR = PROJECT_DIR / "data"
LEADS_FILE = DATA_DIR / "leads.csv"

app = Flask(__name__)
CORS(app)


def save_lead(nombre: str, email: str, empresa: str, repo_url: str, mensaje: str = ""):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    file_exists = LEADS_FILE.exists()

    with open(LEADS_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["nombre", "email", "empresa", "repo_url", "mensaje", "fecha"])
        writer.writerow([nombre, email, empresa, repo_url, mensaje, datetime.now().isoformat()])

    print(f"  ✓ Lead guardado: {nombre} <{email}>")


def add_task(repo_url: str, email: str):
    runner = PROJECT_DIR / "runner.py"
    if not runner.exists():
        print(f"  ⚠️ runner.py no encontrado en {runner}")
        return False

    result = subprocess.run(
        [sys.executable, str(runner), "--add", repo_url, "--email", email],
        capture_output=True, text=True, timeout=30,
        cwd=str(PROJECT_DIR),
    )

    if result.returncode == 0:
        print(f"  ✓ Tarea añadida: {repo_url}")
        return True
    else:
        print(f"  ⚠️ Error al añadir tarea: {result.stderr}")
        return False


@app.route("/submit-lead", methods=["POST"])
def submit_lead():
    data = request.get_json(silent=True) or request.form

    nombre = (data.get("nombre") or "").strip()
    email = (data.get("email") or "").strip()
    empresa = (data.get("empresa") or "").strip()
    repo_url = (data.get("repo_url") or "").strip()
    mensaje = (data.get("mensaje") or "").strip()

    if not nombre or not email:
        return jsonify({"ok": False, "message": "Nombre y email son obligatorios"}), 400

    save_lead(nombre, email, empresa, repo_url, mensaje)

    if repo_url:
        add_task(repo_url, email)

    return jsonify({
        "ok": True,
        "message": "Gracias, en 24h recibirás tu informe gratuito"
    })


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "project": "CodeAudit Pro"})


if __name__ == "__main__":
    port = int(os.getenv("LANDING_PORT", "5001"))
    print(f"🚀 Landing handler en http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)

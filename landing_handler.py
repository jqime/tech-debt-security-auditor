#!/usr/bin/env python3
import csv
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from flask import Flask, Blueprint, jsonify, request

PROJECT_DIR = Path(__file__).parent
DATA_DIR = PROJECT_DIR / "data"
LEADS_FILE = DATA_DIR / "leads.csv"

landing_bp = Blueprint("landing", __name__)


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


@landing_bp.route("/submit-lead", methods=["POST"])
def submit_lead():
    data = request.get_json(silent=True) or request.form

    # Support calculator format: email, sector, size, revenue, compliance_level, source
    if data.get("source") == "calculator":
        email = (data.get("email") or "").strip()
        if not email:
            return jsonify({"ok": False, "message": "Email es obligatorio"}), 400
        save_lead("Lead Calculadora", email, data.get("size", ""), "", f"Calculator: sector={data.get('sector')} revenue={data.get('revenue')} compliance={data.get('compliance_level')}")
        return jsonify({"ok": True, "message": "Resultado calculado"})

    # Legacy format: nombre, email, empresa, repo_url, mensaje
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


PRODUCTS = {
    "auditoria_unica": {"name": "Auditoría Única", "price_cents": 29900},
    "compliance_pro": {"name": "Compliance Pro", "price_cents": 150000},
    "professional": {"name": "Professional", "price_cents": 990000, "interval": "year"},
    "enterprise": {"name": "Enterprise", "price_cents": 2990000, "interval": "year"},
}


@landing_bp.route("/create-checkout-session", methods=["POST"])
def create_checkout_session():
    stripe_key = os.getenv("STRIPE_SECRET_KEY", "")
    if not stripe_key:
        return jsonify({
            "error": "Stripe no configurado",
            "contact": "ventas@codeauditpro.com"
        })

    data = request.get_json(silent=True) or request.form
    plan = data.get("plan", "auditoria_unica")
    repo_url = data.get("repo_url", "")
    customer_email = data.get("customer_email", "")
    demo_id = data.get("demo_id", "")

    if plan not in PRODUCTS:
        return jsonify({"error": f"Plan inválido: {plan}"}), 400

    import stripe
    stripe.api_key = stripe_key

    base_url = os.getenv("BASE_URL", os.getenv("DOMAIN", "http://localhost:5000"))
    prod = PRODUCTS[plan]
    price_data = {
        "currency": "eur",
        "product_data": {"name": prod["name"]},
        "unit_amount": prod["price_cents"],
    }
    if "interval" in prod:
        price_data["recurring"] = {"interval": prod["interval"]}

    mode = "payment" if plan in ("auditoria_unica", "compliance_pro") else "subscription"

    session = stripe.checkout.Session.create(
        mode=mode,
        line_items=[{"price_data": price_data, "quantity": 1}],
        customer_email=customer_email or None,
        payment_method_types=["card", "sepa_debit"],
        metadata={
            "repo_url": repo_url,
            "customer_email": customer_email,
            "plan": plan,
            "demo_id": demo_id,
        },
        success_url=f"{base_url}/dashboard/onboarding?session_id={{CHECKOUT_SESSION_ID}}&plan={plan}",
        cancel_url=f"{base_url}/#precios",
    )
    return jsonify({"url": session.url, "session_id": session.id})


@landing_bp.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "project": "CodeAudit Pro"})

app = Flask(__name__)
app.register_blueprint(landing_bp)

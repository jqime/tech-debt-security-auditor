#!/usr/bin/env python3
import json
import os
import subprocess
import sys
from pathlib import Path

from flask import Flask, jsonify, request

PROJECT_DIR = Path(__file__).parent
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
DOMAIN = os.getenv("DOMAIN", "http://localhost:5001")

app = Flask(__name__)

PRODUCTS = {
    "auditoria_unica": {"name": "Auditoría Única", "price_cents": 29900, "repo_limit": 1},
    "suscripcion_mensual": {"name": "Suscripción Mensual", "price_cents": 19900, "repo_limit": 4},
}


def get_or_create_price(price_id: str) -> str:
    import stripe
    stripe.api_key = STRIPE_SECRET_KEY

    prices = stripe.Price.list(limit=100, currency="eur")
    for p in prices:
        if p.metadata.get("internal_id") == price_id:
            return p.id

    prod = stripe.Product.create(
        name=PRODUCTS[price_id]["name"],
        metadata={"internal_id": price_id},
    )
    price = stripe.Price.create(
        product=prod.id,
        unit_amount=PRODUCTS[price_id]["price_cents"],
        currency="eur",
        metadata={"internal_id": price_id},
    )
    return price.id


def handle_successful_payment(repo_url: str, customer_email: str, user_id: int | None = None):
    print(f"  💳 Pago: {customer_email} -> {repo_url}")
    result = subprocess.run(
        [sys.executable, "runner.py", "--add", repo_url, "--email", customer_email, "--user-id", str(user_id or 0)],
        capture_output=True, text=True, timeout=30,
        cwd=str(PROJECT_DIR),
    )
    if result.returncode == 0:
        print(f"  ✓ Tarea creada para {repo_url}")
    else:
        print(f"  ⚠️ Error: {result.stderr}")
    return True


@app.route("/create-checkout-session", methods=["POST"])
def create_checkout():
    if not STRIPE_SECRET_KEY:
        return jsonify({"error": "STRIPE_SECRET_KEY no configurada. Stripe no está operativo."}), 500

    data = request.get_json(silent=True) or request.form
    price_id = data.get("price_id", "")
    repo_url = data.get("repo_url", "")
    customer_email = data.get("customer_email", "")

    if price_id not in PRODUCTS:
        return jsonify({"error": f"price_id inválido: {price_id}"}), 400

    import stripe
    stripe.api_key = STRIPE_SECRET_KEY

    stripe_price_id = get_or_create_price(price_id)

    session = stripe.checkout.Session.create(
        mode="payment" if price_id != "suscripcion_mensual" else "subscription",
        line_items=[{"price": stripe_price_id, "quantity": 1}],
        customer_email=customer_email,
        metadata={"repo_url": repo_url, "customer_email": customer_email, "price_id": price_id},
        success_url=f"{DOMAIN}/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{DOMAIN}/cancel",
    )

    return jsonify({"url": session.url, "session_id": session.id})


@app.route("/stripe-webhook", methods=["POST"])
def stripe_webhook():
    if not STRIPE_SECRET_KEY:
        return jsonify({"error": "STRIPE_SECRET_KEY no configurada"}), 500

    import stripe
    stripe.api_key = STRIPE_SECRET_KEY

    payload = request.get_data(as_text=True)
    sig_header = request.headers.get("Stripe-Signature", "")
    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET", "")

    if webhook_secret:
        try:
            event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
        except stripe.error.SignatureVerificationError:
            return jsonify({"error": "Firma inválida"}), 400
    else:
        event = json.loads(payload)

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        repo_url = session.get("metadata", {}).get("repo_url", "")
        customer_email = session.get("customer_details", {}).get("email", "") or session.get("metadata", {}).get("customer_email", "")
        if repo_url:
            handle_successful_payment(repo_url, customer_email)

    elif event["type"] == "invoice.paid":
        sub_obj = event["data"]["object"]
        metadata = sub_obj.get("metadata", {})
        repo_url = metadata.get("repo_url", "")
        customer_email = metadata.get("customer_email", "") or sub_obj.get("customer_email", "")
        if repo_url:
            handle_successful_payment(repo_url, customer_email)

    return jsonify({"received": True})


@app.route("/success")
def success():
    return """
    <!DOCTYPE html><html><body style="background:#0b0f19;color:#f8fafc;font-family:sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;">
    <div style="text-align:center"><h1 style="color:#10b981;">✅ Pago exitoso</h1>
    <p>Tu auditoría está en proceso. Recibirás el informe por email en 24h.</p>
    <a href="/" style="color:#818cf8;">Volver a CodeAudit Pro</a></div></body></html>
    """


@app.route("/cancel")
def cancel():
    return """
    <!DOCTYPE html><html><body style="background:#0b0f19;color:#f8fafc;font-family:sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;">
    <div style="text-align:center"><h1 style="color:#f43f5e;">❌ Pago cancelado</h1>
    <p>No se ha realizado ningún cargo. Puedes intentarlo de nuevo cuando quieras.</p>
    <a href="/" style="color:#818cf8;">Volver a CodeAudit Pro</a></div></body></html>
    """


@app.route("/health")
def health():
    stripe_ok = bool(STRIPE_SECRET_KEY)
    return jsonify({"status": "ok", "stripe_configured": stripe_ok, "products": list(PRODUCTS.keys())})


if __name__ == "__main__":
    port = int(os.getenv("PAYMENT_PORT", "5002"))
    print(f"💳 Payment server en http://localhost:{port}")
    print(f"   Stripe: {'✅ configurado' if STRIPE_SECRET_KEY else '❌ sin STRIPE_SECRET_KEY'}")
    app.run(host="0.0.0.0", port=port, debug=False)

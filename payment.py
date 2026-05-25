#!/usr/bin/env python3
import json
import os
import subprocess
import sys
import threading
import uuid
from pathlib import Path

from flask import Flask, jsonify, redirect, render_template_string, request
from werkzeug.security import generate_password_hash

from app.db import get_db

PROJECT_DIR = Path(__file__).parent
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
DOMAIN = os.getenv("DOMAIN", "http://localhost:5001")

app = Flask(__name__)

PRODUCTS = {
    "auditoria_unica": {"name": "Auditoría Única", "price_cents": 29900, "repo_limit": 1},
    "compliance_pro": {"name": "Compliance Pro", "price_cents": 150000, "repo_limit": 10},
    "suscripcion_mensual": {"name": "Suscripción Mensual", "price_cents": 19900, "repo_limit": 4},
    "suscripcion_anual": {"name": "Suscripción Anual", "price_cents": 191000, "repo_limit": 4, "interval": "year"},
    "professional": {"name": "Professional", "price_cents": 990000, "repo_limit": 25, "interval": "year"},
    "enterprise": {"name": "Enterprise", "price_cents": 2990000, "repo_limit": 999, "interval": "year"},
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


def _handle_payment_async(customer_email: str, repo_url: str, plan_type: str, user_id: int = 0, demo_id: str = ""):
    print(f"  💳 Procesando pago: {customer_email} -> {plan_type}")

    try:
        email_script = PROJECT_DIR / "email_sender.py"
        if email_script.exists():
            domain = os.getenv("DOMAIN", "http://localhost:5001")
            welcome_html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="font-family:Arial,sans-serif;padding:20px;background:#f4f4f4;">
<div style="max-width:600px;margin:0 auto;background:white;border-radius:12px;padding:30px;">
    <h2 style="color:#6366f1;">🛡️ ¡Bienvenido a CodeAudit Pro!</h2>
    <p>Gracias por tu compra, <strong>{customer_email}</strong>.</p>
    <p>Tu plan <strong>{plan_type}</strong> está activo. Hemos creado tu cuenta y encolado la auditoría.</p>
    <p style="text-align:center;margin:20px 0;">
        <a href="{domain}/dashboard/onboarding?email={customer_email}&plan={plan_type}" 
           style="display:inline-block;background:#16a34a;color:white;padding:14px 32px;border-radius:8px;text-decoration:none;font-weight:bold;">
           Ir al panel de control →
        </a>
    </p>
    <p style="color:#94a3b8;font-size:12px;">CodeAudit Pro · Cumplimiento NIS2 · DORA · GDPR</p>
</div></body></html>"""
            body_file = PROJECT_DIR / "reports" / "_welcome_email.html"
            body_file.write_text(welcome_html, encoding="utf-8")
            subprocess.run(
                [sys.executable, str(email_script), "--to", customer_email,
                 "--subject", f"Bienvenido a CodeAudit Pro — Plan {plan_type} activado",
                 "--body", str(body_file)],
                cwd=str(PROJECT_DIR), capture_output=True, timeout=30,
            )
    except Exception as e:
        print(f"  ⚠️ Error email bienvenida: {e}")

    if repo_url:
        result = subprocess.run(
            [sys.executable, "runner.py", "--add", repo_url, "--email", customer_email,
             "--plan", plan_type, "--user-id", str(user_id), "--demo-id", demo_id],
            capture_output=True, text=True, timeout=30,
            cwd=str(PROJECT_DIR),
        )
        if result.returncode == 0:
            print(f"  ✓ Tarea creada para {repo_url}")
        else:
            print(f"  ⚠️ Error tarea: {result.stderr}")


@app.route("/create-checkout-session", methods=["POST"])
def create_checkout():
    if not STRIPE_SECRET_KEY:
        return jsonify({"error": "STRIPE_SECRET_KEY no configurada"}), 500

    data = request.get_json(silent=True) or request.form
    plan = data.get("plan", "auditoria_unica")
    repo_url = data.get("repo_url", "")
    customer_email = data.get("customer_email", "")
    demo_id = data.get("demo_id", "")

    if plan not in PRODUCTS:
        return jsonify({"error": f"Plan inválido: {plan}"}), 400

    import stripe
    stripe.api_key = STRIPE_SECRET_KEY
    stripe_price_id = get_or_create_price(plan)

    session = stripe.checkout.Session.create(
        mode="payment" if plan in ("auditoria_unica", "compliance_pro") else "subscription",
        line_items=[{"price": stripe_price_id, "quantity": 1}],
        customer_email=customer_email or None,
        payment_method_types=["card", "sepa_debit"],
        metadata={
            "repo_url": repo_url,
            "customer_email": customer_email,
            "plan": plan,
            "demo_id": demo_id,
        },
        success_url=f"{DOMAIN}/dashboard/onboarding?session_id={{CHECKOUT_SESSION_ID}}&plan={plan}",
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
        metadata = session.get("metadata", {})
        repo_url = metadata.get("repo_url", "")
        customer_email = metadata.get("customer_email", "") or session.get("customer_details", {}).get("email", "")
        plan = metadata.get("plan", "auditoria_unica")
        demo_id = metadata.get("demo_id", "")

        user_id = 0
        if customer_email:
            db = get_db()
            existing = db.execute("SELECT id FROM users WHERE email = ?", (customer_email,)).fetchone()
            if existing:
                user_id = existing["id"]
            else:
                temp_pass = str(uuid.uuid4())[:12]
                phash = generate_password_hash(temp_pass)
                db.execute(
                    "INSERT INTO users (email, password_hash, is_admin) VALUES (?, ?, 0)",
                    (customer_email, phash),
                )
                db.commit()
                row = db.execute("SELECT id FROM users WHERE email = ?", (customer_email,)).fetchone()
                user_id = row["id"] if row else 0
            db.close()

            # Save payment record
            db = get_db()
            db.execute(
                "INSERT INTO payments (user_id, stripe_session_id, amount, currency, status) VALUES (?, ?, ?, ?, 'completed')",
                (user_id, session.get("id", ""), PRODUCTS.get(plan, {}).get("price_cents", 0), "eur"),
            )
            db.commit()
            db.close()

        threading.Thread(
            target=_handle_payment_async,
            args=(customer_email, repo_url, plan, user_id, demo_id),
            daemon=True,
        ).start()

    elif event["type"] == "invoice.paid":
        sub_obj = event["data"]["object"]
        metadata = sub_obj.get("metadata", {})
        repo_url = metadata.get("repo_url", "")
        customer_email = metadata.get("customer_email", "") or sub_obj.get("customer_email", "")
        plan = metadata.get("plan", "suscripcion_mensual")
        if repo_url:
            threading.Thread(
                target=_handle_payment_async,
                args=(customer_email, repo_url, plan),
                daemon=True,
            ).start()

    return jsonify({"received": True})


ONBOARDING_TEMPLATE = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Onboarding — CodeAudit Pro</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#070d1a;color:#f8fafc;font-family:'Segoe UI',system-ui,sans-serif;min-height:100vh;display:flex;align-items:center}
.card{background:#0a1428;border:1px solid rgba(255,255,255,0.08);border-radius:16px;padding:2.5rem;max-width:560px;margin:2rem auto;box-shadow:0 20px 60px rgba(0,0,0,0.4);text-align:center}
h1{font-size:1.5rem;font-weight:700;color:#f1f5f9;margin-bottom:0.5rem}
.sub{color:#64748b;font-size:0.9rem;margin-bottom:1.5rem}
.check-icon{font-size:3.5rem;margin-bottom:1rem}
.progress{height:8px;background:rgba(255,255,255,0.06);border-radius:100px;overflow:hidden;margin:1.5rem 0}
.progress-bar{background:linear-gradient(90deg,#f59e0b,#10b981);border-radius:100px;transition:width 0.5s}
.status-text{color:#94a3b8;font-size:0.85rem;margin:0.5rem 0}
.plan-badge{display:inline-flex;align-items:center;gap:6px;background:rgba(245,158,11,0.12);border:1px solid rgba(245,158,11,0.2);border-radius:100px;padding:6px 14px;font-size:0.72rem;color:#f59e0b;margin-bottom:1rem}
.btn-primary{display:inline-block;padding:14px 36px;border-radius:10px;background:linear-gradient(135deg,#f59e0b,#d97706);color:#070d1a;font-weight:700;text-decoration:none;transition:all 0.2s;border:none;font-size:0.95rem;cursor:pointer}
.btn-primary:hover{transform:translateY(-2px);box-shadow:0 8px 30px rgba(245,158,11,0.3)}
.btn-secondary{display:inline-block;padding:12px 28px;border-radius:10px;background:rgba(255,255,255,0.08);color:#e2e8f0;text-decoration:none;font-weight:500;font-size:0.9rem;margin-top:0.5rem}
.btn-secondary:hover{background:rgba(255,255,255,0.12)}
.steps{text-align:left;margin:1.5rem 0}
.step{display:flex;align-items:center;gap:10px;padding:8px 0;font-size:0.85rem;color:#64748b}
.step.done{color:#10b981}
.step.active{color:#f59e0b}
.text-muted{color:#64748b}
</style>
</head>
<body>
<div class="container">
<div class="card" id="onboardingCard">
<div class="check-icon" id="statusIcon">✅</div>
<h1 id="title">¡Pago recibido con éxito!</h1>
<p class="sub" id="subtitle">Tu plan <strong>{{ plan }}</strong> está activo. Estamos preparando tu auditoría.</p>

<div class="plan-badge">⚡ {{ plan }}</div>

<div class="progress">
<div class="progress-bar" id="progressBar" style="width:{{ progress }}%"></div>
</div>
<p class="status-text" id="statusText">{% if task_id %}{{ status }}{% else %}Preparando tu cuenta...{% endif %}</p>

<div class="steps" id="stepsContainer">
<div class="step {% if progress >= 20 %}done{% endif %}" id="step-payment">
<span class="step-icon">{% if progress >= 20 %}✅{% else %}⏳{% endif %}</span> Pago verificado
</div>
<div class="step {% if progress >= 40 %}done{% endif %}" id="step-account">
<span class="step-icon">{% if progress >= 40 %}✅{% else %}⏳{% endif %}</span> Cuenta creada
</div>
<div class="step {% if progress >= 60 %}done{% endif %}" id="step-audit">
<span class="step-icon">{% if progress >= 60 %}✅{% else %}⏳{% endif %}</span> Auditoría en cola
</div>
<div class="step" id="step-done">
<span class="step-icon">{% if progress >= 80 %}✅{% else %}⏳{% endif %}</span> Informe generado
</div>
</div>

{% if progress >= 80 %}
<a href="/dashboard/" class="btn-primary">Ir al Dashboard →</a>
<br>
<a href="/reports/executive-report.html" class="btn-secondary">📄 Ver informe preliminar</a>
{% endif %}

<p class="text-muted" style="font-size:0.75rem;margin-top:1rem">
Te hemos enviado un email de confirmación a <strong>{{ email }}</strong>
</p>
</div>
</div>
<script>
{% if task_id %}
const TASK_ID = '{{ task_id }}';
const POLL = setInterval(async () => {{
  try {{
    const resp = await fetch('/api/task/' + TASK_ID + '/status');
    const data = await resp.json();
    const pctMap = {{'pending':30,'running':60,'done':100,'failed':100}};
    const pct = pctMap[data.status] || 30;
    document.getElementById('progressBar').style.width = pct + '%';
    document.getElementById('statusText').textContent = 'Estado: ' + data.status;
    if (data.status === 'done') {{
      clearInterval(POLL);
      document.getElementById('statusIcon').textContent = '🎉';
      document.getElementById('title').textContent = '¡Tu informe está listo!';
      document.getElementById('subtitle').innerHTML = 'Descarga tu informe de auditoría completo.';
      document.getElementById('step-done').className = 'step done';
      document.getElementById('step-done').querySelector('.step-icon').textContent = '✅';
      document.getElementById('stepsContainer').insertAdjacentHTML('afterend',
        '<a href="/reports/executive-report.html" class="btn-primary mt-3">📄 Descargar informe</a>' +
        '<br><a href="/dashboard/" class="btn-secondary mt-2">Ir al Dashboard</a>');
    }}
  }} catch(e) {{}}
}}, 3000);
{% endif %}
</script>
</body>
</html>"""


@app.route("/dashboard/onboarding")
def onboarding():
    session_id = request.args.get("session_id", "")
    plan = request.args.get("plan", "auditoria_unica")
    email = request.args.get("email", "")
    progress = 0
    task_id = None
    status = "pending"

    if email:
        progress = 20
        db = get_db()
        user = db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if user:
            progress = 40
            task = db.execute(
                "SELECT id, status FROM tasks WHERE user_id = ? ORDER BY created_at DESC LIMIT 1",
                (user["id"],),
            ).fetchone()
            if task:
                task_id = task["id"]
                status = task["status"]
                progress = 80 if status == "done" else 60 if status == "running" else 50
        db.close()
    elif session_id:
        import stripe
        stripe.api_key = STRIPE_SECRET_KEY
        try:
            session = stripe.checkout.Session.retrieve(session_id)
            email = session.get("customer_details", {}).get("email", "") or session.get("customer_email", "")
            metadata = session.get("metadata", {})
            plan = metadata.get("plan", plan)
            if email:
                return redirect(f"/dashboard/onboarding?email={email}&plan={plan}")
        except Exception:
            pass

    return render_template_string(
        ONBOARDING_TEMPLATE,
        plan=plan,
        email=email,
        progress=progress,
        task_id=task_id,
        status=status,
    )


@app.route("/api/task/<int:task_id>/status")
def task_status(task_id):
    db = get_db()
    row = db.execute("SELECT id, status, created_at, finished_at FROM tasks WHERE id = ?", (task_id,)).fetchone()
    db.close()
    if row:
        return jsonify(dict(row))
    return jsonify({"error": "Tarea no encontrada"}), 404


@app.route("/success")
def success():
    return """
    <!DOCTYPE html><html><body style="background:#0b0f19;color:#f8fafc;font-family:sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;">
    <div style="text-align:center"><h1 style="color:#10b981;">✅ Pago exitoso</h1>
    <p>Tu auditoría está en proceso. Recibirás el informe por email.</p>
    <p style="color:#94a3b8;font-size:14px;">Factura PDF disponible en tu panel de control.</p>
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

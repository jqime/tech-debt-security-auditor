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
BASE_URL = os.getenv("BASE_URL", os.getenv("DOMAIN", "http://localhost:5000"))

app = Flask(__name__)

PRODUCTS = {
    "auditoria_unica": {"name": "Auditoría Única", "price_cents": 29900, "repo_limit": 1},
    "compliance_pro": {"name": "Compliance Pro", "price_cents": 150000, "repo_limit": 10},
    "suscripcion_mensual": {"name": "Suscripción Mensual", "price_cents": 19900, "repo_limit": 4},
    "suscripcion_anual": {"name": "Suscripción Anual", "price_cents": 191000, "repo_limit": 4, "interval": "year"},
    "professional": {"name": "Professional", "price_cents": 990000, "repo_limit": 25, "interval": "year"},
    "enterprise": {"name": "Enterprise", "price_cents": 2990000, "repo_limit": 999, "interval": "year"},
}


def _handle_payment_async(customer_email: str, repo_url: str, plan_type: str, user_id: int = 0, demo_id: str = ""):
    print(f"  💳 Procesando pago: {customer_email} -> {plan_type}")
    try:
        email_script = PROJECT_DIR / "email_sender.py"
        if email_script.exists():
            domain = BASE_URL
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
    stripe.api_key = STRIPE_SECRET_KEY

    mode = "payment" if plan in ("auditoria_unica", "compliance_pro") else "subscription"
    price_data = {
        "currency": "eur",
        "product_data": {"name": PRODUCTS[plan]["name"]},
        "unit_amount": PRODUCTS[plan]["price_cents"],
    }
    if "interval" in PRODUCTS[plan]:
        price_data["recurring"] = {"interval": PRODUCTS[plan]["interval"]}

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
        success_url=f"{BASE_URL}/dashboard/onboarding?session_id={{CHECKOUT_SESSION_ID}}&plan={plan}",
        cancel_url=f"{BASE_URL}/#precios",
    )
    return jsonify({"url": session.url, "session_id": session.id})


@app.route("/stripe-webhook", methods=["POST"])
def stripe_webhook():
    if not STRIPE_SECRET_KEY:
        return jsonify({"error": "Stripe no configurado"}), 500

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

            db = get_db()
            existing_payment = db.execute(
                "SELECT id FROM payments WHERE stripe_session_id = ?", (session.get("id", ""),
            )).fetchone()
            if existing_payment:
                print(f"  ⚠️ Evento duplicado ignorado (session {session.get('id', '')})")
            else:
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
    elif session_id and STRIPE_SECRET_KEY:
        import stripe
        stripe.api_key = STRIPE_SECRET_KEY
        try:
            session = stripe.checkout.Session.retrieve(session_id)
            email = session.get("customer_details", {}).get("email", "") or session.get("customer_email", "")
            metadata = session.get("metadata", {})
            plan = metadata.get("plan", plan)
            if email and session.get("payment_status") == "paid":
                    db = get_db()
                    existing = db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
                    if not existing:
                        from werkzeug.security import generate_password_hash
                        temp_pass = str(uuid.uuid4())[:12]
                        db.execute(
                            "INSERT INTO users (email, password_hash, is_admin) VALUES (?, ?, 0)",
                            (email, generate_password_hash(temp_pass)),
                        )
                        db.commit()
                        row = db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
                        user_id = row["id"] if row else 0
                    else:
                        user_id = existing["id"]
                    existing_payment = db.execute(
                        "SELECT id FROM payments WHERE stripe_session_id = ?", (session.get("id", ""),
                    )).fetchone()
                    if not existing_payment and user_id:
                        db.execute(
                            "INSERT INTO payments (user_id, stripe_session_id, amount, currency, status) VALUES (?, ?, ?, ?, 'completed')",
                            (user_id, session.get("id", ""),
                             PRODUCTS.get(plan, {}).get("price_cents", 0) if "PRODUCTS" in dir() else 0, "eur"),
                        )
                        db.commit()
                    db.close()
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


# ── Abandoned Cart Recovery ─────────────────────────────────────

def _send_discount_email(email: str, discount_pct: int = 10):
    """Envía email de recuperación con descuento por tiempo limitado."""
    try:
        email_script = PROJECT_DIR / "email_sender.py"
        if not email_script.exists():
            return
        discount_code = f"RECUPERA{discount_pct}"
        checkout_url = f"{BASE_URL}/create-checkout?plan=compliance_pro&email={email}&coupon={discount_code}"
        html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="font-family:Arial,sans-serif;padding:20px;background:#f4f4f4;">
<div style="max-width:600px;margin:0 auto;background:white;border-radius:16px;padding:32px;border:2px solid #f59e0b;">
<div style="text-align:center;margin-bottom:16px;">
<span style="display:inline-block;background:#f59e0b;color:#111827;padding:6px 20px;border-radius:100px;font-size:0.75rem;font-weight:700;text-transform:uppercase;">⏰ Oferta exclusiva · 24h</span>
</div>
<h2 style="color:#111827;text-align:center;">¿Te olvidaste de tu auditoría?</h2>
<p style="color:#6b7280;text-align:center;margin-bottom:16px;">
Tu análisis de seguridad está completo y te está esperando. Durante las próximas <strong>24 horas</strong> puedes desbloquear el informe completo con un <strong>{discount_pct}% de descuento</strong>.
</p>
<div style="background:#fffbeb;border:1px solid #fde68a;border-radius:12px;padding:20px;margin-bottom:20px;text-align:center;">
<p style="color:#92400e;font-size:0.85rem;margin-bottom:4px;">Código de descuento:</p>
<p style="font-family:monospace;font-size:1.5rem;font-weight:800;color:#f59e0b;letter-spacing:0.1em;">{discount_code}</p>
<p style="color:#92400e;font-size:0.78rem;">{discount_pct}% de descuento · Válido 24h</p>
</div>
<div style="text-align:center;margin:20px 0;">
<a href="{checkout_url}" style="display:inline-block;background:linear-gradient(135deg,#f59e0b,#d97706);color:#111827;padding:16px 48px;border-radius:12px;text-decoration:none;font-weight:700;font-size:1.05rem;box-shadow:0 4px 20px rgba(245,158,11,0.3);">
DESBLOQUEAR CON {discount_pct}% OFF →
</a>
</div>
<p style="color:#9ca3af;font-size:0.72rem;text-align:center;">
Tu informe incluye: compliance NIS2/DORA · PDF certificado · Plan de remediación · Validez legal
</p>
<div style="border-top:1px solid #e5e7eb;margin-top:24px;padding-top:16px;text-align:center;color:#9ca3af;font-size:0.72rem;">
CodeAudit Pro · Cumplimiento NIS2/DORA para PYMEs<br>
<a href="{BASE_URL}/unsubscribe?email={email}" style="color:#9ca3af;">Darme de baja</a>
</div></div></body></html>"""
        body_file = PROJECT_DIR / "reports" / "_recovery_email.html"
        body_file.write_text(html, encoding="utf-8")
        subprocess.run(
            [sys.executable, str(email_script), "--to", email,
             "--subject", f"⏰ {discount_pct}% de descuento — tu auditoría te espera",
             "--body", str(body_file)],
            cwd=str(PROJECT_DIR), capture_output=True, timeout=30,
        )
        print(f"  📧 Email recuperación enviado a {email} (código: {discount_code})")
    except Exception as e:
        print(f"  ⚠️ Error email recuperación: {e}")


def _recover_abandoned_carts():
    """Busca leads sin pago > 2h y envía email de recuperación."""
    from datetime import datetime, timedelta
    try:
        db = get_db()
        cutoff = (datetime.now() - timedelta(hours=2)).isoformat()
        rows = db.execute(
            """SELECT DISTINCT l.email, l.repo_url
               FROM leads l
               LEFT JOIN users u ON l.email = u.email
               LEFT JOIN payments p ON u.id = p.user_id
               WHERE l.created_at < ?
               AND (p.id IS NULL OR p.status != 'completed')
               AND l.email NOT IN (
                   SELECT email FROM leads WHERE mensaje LIKE '%recovery_sent%'
               )""",
            (cutoff,),
        ).fetchall()
        db.close()

        for row in rows:
            email = row["email"]
            _send_discount_email(email, discount_pct=10)
            # Marcar recovery como enviado
            db2 = get_db()
            db2.execute(
                "UPDATE leads SET mensaje = mensaje || ' | recovery_sent' WHERE email = ? AND mensaje NOT LIKE '%recovery_sent%'",
                (email,),
            )
            db2.commit()
            db2.close()

        if rows:
            print(f"  📬 Recuperación: {len(rows)} carritos abandonados")
    except Exception as e:
        print(f"  ⚠️ Error en recuperación de carritos: {e}")


def start_recovery_scheduler():
    """Inicia el scheduler de recuperación de carritos abandonados (cada 30 min)."""
    from apscheduler.schedulers.background import BackgroundScheduler
    try:
        scheduler = BackgroundScheduler()
        scheduler.add_job(_recover_abandoned_carts, "interval", minutes=30, id="abandoned_cart_recovery")
        scheduler.start()
        print("  📅 Scheduler de recuperación iniciado (cada 30 min)")
        return scheduler
    except Exception as e:
        print(f"  ⚠️ No se pudo iniciar scheduler: {e}")
        return None


if __name__ == "__main__":
    port = int(os.getenv("PAYMENT_PORT", "5002"))
    print(f"💳 Payment server en http://localhost:{port}")
    print(f"   Stripe: {'✅ configurado' if STRIPE_SECRET_KEY else '❌ sin STRIPE_SECRET_KEY'}")
    recovery_scheduler = start_recovery_scheduler()
    try:
        app.run(host="0.0.0.0", port=port, debug=False)
    finally:
        if recovery_scheduler:
            recovery_scheduler.shutdown()

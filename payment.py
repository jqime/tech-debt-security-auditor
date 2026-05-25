#!/usr/bin/env python3
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT_DIR = Path(__file__).parent
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")

PRODUCTS = {
    "auditoria_unica": {"name": "Auditoría Única", "price_cents": 29900, "repo_limit": 1},
    "suscripcion_mensual": {"name": "Suscripción Mensual", "price_cents": 19900, "repo_limit": 4},
}


def setup_stripe_products():
    if not STRIPE_SECRET_KEY:
        print("ℹ️  Modo simulado: no hay STRIPE_SECRET_KEY")
        print("   Define la variable de entorno para usar Stripe real.")
        return

    import stripe
    stripe.api_key = STRIPE_SECRET_KEY

    for pid, product in PRODUCTS.items():
        print(f"  Creando producto: {product['name']}...")
        stripe_prod = stripe.Product.create(name=product["name"])
        stripe.Price.create(
            product=stripe_prod.id,
            unit_amount=product["price_cents"],
            currency="eur",
        )
        print(f"  ✓ Producto {product['name']} creado (ID: {stripe_prod.id})")


def create_checkout_session(price_id: str, repo_url: str, customer_email: str) -> str | None:
    if not STRIPE_SECRET_KEY:
        print(f"ℹ️  Modo simulado: checkout para {price_id} - {customer_email}")
        return "cs_simulated_checkout_id"

    import stripe
    stripe.api_key = STRIPE_SECRET_KEY

    session = stripe.checkout.Session.create(
        mode="payment" if price_id != "suscripcion_mensual" else "subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        customer_email=customer_email,
        metadata={"repo_url": repo_url},
        success_url="https://tudominio.com/success?session_id={CHECKOUT_SESSION_ID}",
        cancel_url="https://tudominio.com/cancel",
    )
    return session.url


def handle_successful_payment(repo_url: str, customer_email: str):
    print(f"  💳 Pago recibido: {customer_email} -> {repo_url}")
    print(f"  🚀 Iniciando auditoría para: {repo_url}")
    result = subprocess.run(
        ["./run-audit.sh", repo_url],
        capture_output=True, text=True, timeout=600,
        cwd=str(PROJECT_DIR),
    )
    if result.returncode != 0:
        print(f"  ❌ Error en auditoría: {result.stderr}")
        return False

    print(f"  ✓ Auditoría completada. Enviando informe...")

    report_path = PROJECT_DIR / "reports" / "executive-report.html"
    if not report_path.exists():
        print(f"  ❌ No se encontró el informe: {report_path}")
        return False

    email_script = PROJECT_DIR / "email_sender.py"
    if email_script.exists():
        subprocess.run(
            [sys.executable, str(email_script),
             "--to", customer_email,
             "--subject", f"Informe de auditoría - {repo_url}",
             "--attach", str(report_path)],
            cwd=str(PROJECT_DIR),
        )

    tasks_file = PROJECT_DIR / "data" / "tasks.json"
    if tasks_file.exists():
        try:
            tasks = json.loads(tasks_file.read_text())
            for t in tasks:
                if t.get("repo_url") == repo_url and t.get("status") == "pending":
                    t["status"] = "completed"
            tasks_file.write_text(json.dumps(tasks, indent=2))
        except Exception:
            pass

    return True


def handle_stripe_webhook(payload: dict):
    event_type = payload.get("type", "")
    if event_type == "checkout.session.completed":
        session = payload.get("data", {}).get("object", {})
        repo_url = session.get("metadata", {}).get("repo_url", "")
        customer_email = session.get("customer_details", {}).get("email", "")
        if repo_url:
            handle_successful_payment(repo_url, customer_email)
    elif event_type == "invoice.paid":
        subscription = payload.get("data", {}).get("object", {})
        metadata = subscription.get("metadata", {})
        repo_url = metadata.get("repo_url", "")
        customer_email = subscription.get("customer_email", "")
        if repo_url:
            handle_successful_payment(repo_url, customer_email)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Integración de pagos Stripe")
    parser.add_argument("--setup", action="store_true", help="Crear productos en Stripe")
    parser.add_argument("--checkout", help="ID de precio para crear sesión de checkout")
    parser.add_argument("--repo", help="URL del repositorio a auditar")
    parser.add_argument("--email", help="Email del cliente")
    parser.add_argument("--webhook", help="JSON de evento webhook de Stripe (ruta a archivo o '-' para stdin)")

    args = parser.parse_args()

    if args.setup:
        setup_stripe_products()
    elif args.checkout:
        url = create_checkout_session(args.checkout, args.repo or "", args.email or "")
        if url:
            print(f"URL de checkout: {url}")
    elif args.webhook:
        if args.webhook == "-":
            payload = json.loads(sys.stdin.read())
        else:
            payload = json.loads(Path(args.webhook).read_text())
        handle_stripe_webhook(payload)
        print("Webhook procesado.")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

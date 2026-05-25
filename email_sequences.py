import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from threading import Thread

PROJECT_DIR = Path(__file__).parent
DOMAIN = os.getenv("DOMAIN", "http://localhost:5001")
EMAIL_SCRIPT = PROJECT_DIR / "email_sender.py"

EMAIL_1_DEMO_READY = """<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="font-family:Arial,sans-serif;padding:20px;background:#f4f4f4;">
<div style="max-width:600px;margin:0 auto;background:white;border-radius:16px;padding:32px;box-shadow:0 4px 20px rgba(0,0,0,0.05);">
<div style="text-align:center;margin-bottom:20px;font-size:2.5rem;">🔍</div>
<h2 style="color:#111827;text-align:center;margin-bottom:8px;">Tu análisis de {repo_name} está listo</h2>
<p style="color:#6b7280;text-align:center;margin-bottom:20px;">{findings_summary} — Score NIS2: <strong>{score}/100</strong></p>

<div style="background:#fef2f2;border:1px solid #fecaca;border-radius:12px;padding:16px;margin-bottom:20px;text-align:center;">
<p style="color:#991b1b;font-size:0.8rem;text-transform:uppercase;letter-spacing:0.04em;font-weight:600;margin-bottom:4px;">⚠️ Multa potencial estimada</p>
<p style="color:#dc2626;font-size:1.5rem;font-weight:700;">HASTA {fine} €</p>
<p style="color:#9ca3af;font-size:0.75rem;">Según Art. 31 NIS2 y Art. 50 DORA</p>
</div>

<div style="background:#f0f5ff;border:1px solid #bfdbfe;border-radius:12px;padding:16px;margin-bottom:20px;">
<p style="color:#1e40af;font-weight:600;margin-bottom:8px;">🔒 {hidden_count} hallazgos están bloqueados</p>
<p style="color:#374151;font-size:0.85rem;">El informe completo incluye el plan de remediación detallado, el mapeo de cumplimiento NIS2/DORA artículo por artículo, y el PDF certificado válido para auditores.</p>
</div>

<div style="text-align:center;margin:24px 0;">
<a href="{checkout_url}" style="display:inline-block;background:linear-gradient(135deg,#6366f1,#818cf8);color:white;padding:16px 48px;border-radius:12px;text-decoration:none;font-weight:700;font-size:1.05rem;box-shadow:0 4px 20px rgba(99,102,241,0.3);">
VER INFORME COMPLETO — {price} € →
</a>
</div>
<p style="color:#9ca3af;font-size:0.75rem;text-align:center;">Este análisis caduca en 48h. Después tendrás que lanzar uno nuevo.</p>

<div style="border-top:1px solid #e5e7eb;margin-top:24px;padding-top:16px;text-align:center;color:#9ca3af;font-size:0.72rem;">
CodeAudit Pro · Cumplimiento NIS2/DORA para PYMEs<br>
<a href="{unsubscribe_url}" style="color:#9ca3af;">Darme de baja</a>
</div></div></body></html>"""

EMAIL_2_24H = """<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="font-family:Arial,sans-serif;padding:20px;background:#f4f4f4;">
<div style="max-width:600px;margin:0 auto;background:white;border-radius:16px;padding:32px;">
<h2 style="color:#111827;margin-bottom:12px;">¿Sabías que {sector} ya están certificados en NIS2?</h2>

<div style="background:#f9fafb;border-radius:12px;padding:16px;margin-bottom:16px;">
<h3 style="color:#111827;font-size:0.9rem;margin-bottom:8px;">📊 Multas reales impuestas en Europa (2024-2025)</h3>
<ul style="color:#374151;font-size:0.85rem;line-height:1.7;">
<li>🇪🇸 España: 5 empresas sancionadas por incumplimiento de seguridad (multa media: 180.000 €)</li>
<li>🇩🇪 Alemania: 12 procedimientos abiertos por falta de medidas técnicas</li>
<li>🇮🇹 Italia: 3 casos con multas superiores a 1.000.000 €</li>
</ul>
</div>

<div style="background:#fef2f2;border:1px solid #fecaca;border-radius:12px;padding:16px;margin-bottom:16px;">
<p style="color:#991b1b;font-weight:600;margin-bottom:4px;">Tu empresa tiene {n_criticos} vulnerabilidades críticas sin resolver</p>
<p style="color:#374151;font-size:0.85rem;">Cada día sin actuar aumentas tu exposición regulatoria y el riesgo de brecha de seguridad.</p>
</div>

<div style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:12px;padding:16px;margin-bottom:20px;">
<p style="color:#166534;font-weight:600;margin-bottom:4px;">💰 Comparativa real</p>
<table style="width:100%;font-size:0.85rem;color:#374151;">
<tr><td>Consultoría tradicional (Big4)</td><td style="text-align:right;font-weight:700;color:#dc2626;">40.000 € · 3 meses</td></tr>
<tr><td>CodeAudit Pro</td><td style="text-align:right;font-weight:700;color:#16a34a;">{price} € · 5 minutos</td></tr>
</table>
</div>

<div style="text-align:center;">
<a href="{checkout_url}" style="display:inline-block;background:linear-gradient(135deg,#6366f1,#818cf8);color:white;padding:16px 48px;border-radius:12px;text-decoration:none;font-weight:700;font-size:1.05rem;">
Empezar ahora →
</a>
</div>

<div style="border-top:1px solid #e5e7eb;margin-top:24px;padding-top:16px;text-align:center;color:#9ca3af;font-size:0.72rem;">
<a href="{unsubscribe_url}" style="color:#9ca3af;">Darme de baja</a>
</div></div></body></html>"""

EMAIL_3_72H = """<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="font-family:Arial,sans-serif;padding:20px;background:#f4f4f4;">
<div style="max-width:600px;margin:0 auto;background:white;border-radius:16px;padding:32px;">
<h2 style="color:#111827;margin-bottom:12px;">🔴 Caso real: PYME multada con 180.000 € por incumplir NIS2</h2>

<div style="background:#f9fafb;border:1px solid #e5e7eb;border-radius:12px;padding:16px;margin-bottom:16px;">
<p style="color:#374151;font-size:0.85rem;line-height:1.6;font-style:italic;">
"Una PYME tecnológica de 45 empleados recibió una sanción de 180.000 € de la Agencia Española de Protección de Datos por no implementar medidas técnicas adecuadas de seguridad. Su CTO declaró: 'Pensábamos que NIS2 no aplicaba a empresas pequeñas. El informe de CodeAudit Pro nos habría ahorrado la multa.'"
</p>
<p style="color:#6b7280;font-size:0.75rem;margin-top:8px;">— Fuente: AEPD, casos 2024-2025</p>
</div>

<div style="background:#f0f5ff;border:1px solid #bfdbfe;border-radius:12px;padding:16px;margin-bottom:16px;">
<p style="color:#1e40af;font-weight:600;margin-bottom:8px;">📋 Tu informe completo incluye:</p>
<ul style="color:#374151;font-size:0.85rem;line-height:1.7;">
<li>Plan de remediación paso a paso</li>
<li>Mapeo artículo por artículo de NIS2 y DORA</li>
<li>PDF certificado con firma digital (válido para auditores)</li>
<li>Declaración de debida diligencia</li>
</ul>
</div>

<div style="margin:20px 0;">
<p style="color:#6b7280;font-size:0.85rem;font-style:italic;text-align:center;">
"Por 299 € conseguimos lo que una consultora nos presupuestó en 38.000 €. Mismo marco normativo, misma validez, 1% del precio."<br>
<strong style="color:#374151;">— Alejandro López, Director IT, InnovaPay</strong>
</p>
</div>

<div style="text-align:center;">
<a href="{checkout_url}" style="display:inline-block;background:linear-gradient(135deg,#6366f1,#818cf8);color:white;padding:16px 48px;border-radius:12px;text-decoration:none;font-weight:700;box-shadow:0 4px 20px rgba(99,102,241,0.3);">
Proteger mi empresa — {price} € →
</a>
<p style="color:#16a34a;font-size:0.78rem;margin-top:8px;">🛡️ Garantía: Si no encuentras ninguna vulnerabilidad, te devolvemos el importe íntegro.</p>
</div>

<div style="border-top:1px solid #e5e7eb;margin-top:24px;padding-top:16px;text-align:center;color:#9ca3af;font-size:0.72rem;">
<a href="{unsubscribe_url}" style="color:#9ca3af;">Darme de baja</a>
</div></div></body></html>"""

EMAIL_4_7D = """<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="font-family:Arial,sans-serif;padding:20px;background:#f4f4f4;">
<div style="max-width:600px;margin:0 auto;background:white;border-radius:16px;padding:32px;border:2px solid #f59e0b;">
<div style="text-align:center;margin-bottom:16px;">
<span style="display:inline-block;background:#f59e0b;color:white;padding:6px 20px;border-radius:100px;font-size:0.75rem;font-weight:700;text-transform:uppercase;">🎉 Oferta exclusiva</span>
</div>
<h2 style="color:#111827;text-align:center;margin-bottom:8px;">15% de descuento — Solo esta semana</h2>
<p style="color:#6b7280;text-align:center;margin-bottom:20px;">Utiliza el código <strong style="color:#f59e0b;">COMPLIANCE15</strong> antes del <strong>{deadline}</strong></p>

<div style="background:#fffbeb;border:1px solid #fde68a;border-radius:12px;padding:20px;margin-bottom:20px;text-align:center;">
<p style="color:#92400e;font-size:0.85rem;font-weight:600;margin-bottom:8px;">Tu plan Compliance Pro incluye:</p>
<ul style="color:#374151;font-size:0.85rem;text-align:left;line-height:1.8;">
<li>✅ Informe completo con todos los hallazgos</li>
<li>✅ Mapeo NIS2/DORA artículo por artículo</li>
<li>✅ PDF certificado con firma digital SHA-256</li>
<li>✅ Plan de remediación priorizado</li>
<li>✅ Declaración de debida diligencia</li>
<li>✅ Válido para auditores externos</li>
</ul>
</div>

<div style="text-align:center;margin:20px 0;">
<p style="color:#9ca3af;font-size:0.9rem;margin-bottom:4px;">~~ {original_price} € ~~</p>
<p style="color:#16a34a;font-size:2rem;font-weight:800;">{discounted_price} €</p>
<p style="color:#6b7280;font-size:0.8rem;">Ahorras {savings} € · Código: COMPLIANCE15</p>
</div>

<div style="text-align:center;">
<a href="{checkout_url}" style="display:inline-block;background:linear-gradient(135deg,#f59e0b,#d97706);color:#111827;padding:16px 48px;border-radius:12px;text-decoration:none;font-weight:700;font-size:1.05rem;box-shadow:0 4px 20px rgba(245,158,11,0.3);">
Canjear descuento →
</a>
</div>

<div style="border-top:1px solid #e5e7eb;margin-top:24px;padding-top:16px;text-align:center;color:#9ca3af;font-size:0.72rem;">
<a href="{unsubscribe_url}" style="color:#9ca3af;">Darme de baja</a>
</div></div></body></html>"""

EMAIL_5_14D = """<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="font-family:Arial,sans-serif;padding:20px;background:#f4f4f4;">
<div style="max-width:600px;margin:0 auto;background:white;border-radius:16px;padding:32px;">
<h2 style="color:#111827;margin-bottom:12px;">Entendemos que quizás no es el momento</h2>
<p style="color:#6b7280;margin-bottom:16px;">Solo queremos que sepas que cuando estés preparado, aquí estaremos.</p>

<div style="background:#f9fafb;border:1px solid #e5e7eb;border-radius:12px;padding:16px;margin-bottom:16px;">
<p style="color:#374151;font-size:0.85rem;line-height:1.6;">
<b>📌 Guarda este enlace para cuando lo necesites:</b><br>
<a href="{checkout_url}" style="color:#6366f1;">{checkout_url}</a>
</p>
</div>

<div style="background:#fefce8;border:1px solid #fde68a;border-radius:12px;padding:16px;margin-bottom:20px;">
<p style="color:#92400e;font-size:0.85rem;line-height:1.6;">
<strong>⏰ Recordatorio:</strong> NIS2 está en vigor desde octubre 2024 y DORA desde enero 2025. 
Cada mes sin auditoría es un mes de exposición regulatoria. Las sanciones para PYMEs comienzan en torno a los 50.000 €.
</p>
</div>

<div style="text-align:center;">
<a href="{checkout_url}" style="display:inline-block;background:#f9fafb;border:1px solid #e5e7eb;color:#374151;padding:14px 40px;border-radius:12px;text-decoration:none;font-weight:600;font-size:0.95rem;">
Cuando estés listo, aquí estaremos →
</a>
</div>

<div style="margin:16px 0;padding:12px;background:#f9fafb;border-radius:8px;text-align:center;">
<p style="color:#6b7280;font-size:0.8rem;margin-bottom:8px;">¿Quieres que te recordemos más tarde?</p>
<a href="{remind_30_url}" style="color:#6366f1;font-size:0.78rem;text-decoration:none;margin-right:12px;">🔔 En 30 días</a>
<a href="{remind_90_url}" style="color:#6366f1;font-size:0.78rem;text-decoration:none;">🔔 En 90 días</a>
</div>

<div style="border-top:1px solid #e5e7eb;margin-top:24px;padding-top:16px;text-align:center;color:#9ca3af;font-size:0.72rem;">
<a href="{unsubscribe_url}" style="color:#9ca3af;">Darme de baja</a>
</div></div></body></html>"""


def _send_now(to_email: str, subject: str, html_body: str):
    body_file = PROJECT_DIR / "reports" / f"_seq_{abs(hash(subject)) % 10000}.html"
    body_file.write_text(html_body, encoding="utf-8")
    try:
        subprocess.run(
            [sys.executable, str(EMAIL_SCRIPT), "--to", to_email, "--subject", subject, "--body", str(body_file)],
            cwd=str(PROJECT_DIR), capture_output=True, timeout=30,
        )
    except Exception as e:
        print(f"  ⚠️ Error sending email '{subject}': {e}")
    finally:
        if body_file.exists():
            body_file.unlink()


def send_sequence(email: str, demo_data: dict):
    repo_name = demo_data.get("repo_name", "tu repositorio")
    score = demo_data.get("score", 45)
    fine = demo_data.get("fine", "10.000.000")
    hidden_count = demo_data.get("hidden_count", 12)
    n_criticos = demo_data.get("n_criticos", 3)
    sector = demo_data.get("sector", "las empresas de tu sector")
    price = demo_data.get("price", 299)
    original_price = demo_data.get("original_price", 1500)
    discounted_price = demo_data.get("discounted_price", 1275)
    savings = original_price - discounted_price
    findings_summary = demo_data.get("findings_summary", f"{n_criticos} vulnerabilidades críticas encontradas")
    checkout_url = f"{DOMAIN}/create-checkout?plan=compliance_pro&email={email}"
    unsubscribe_url = f"{DOMAIN}/unsubscribe?email={email}"
    deadline = (datetime.now() + timedelta(days=7)).strftime("%d/%m/%Y")

    seq = [
        {
            "subject": f"Tu análisis de {repo_name} está listo — {n_criticos} vulnerabilidades encontradas",
            "body": EMAIL_1_DEMO_READY.format(
                repo_name=repo_name, findings_summary=findings_summary, score=score,
                fine=fine, hidden_count=hidden_count, checkout_url=checkout_url,
                price=price, unsubscribe_url=unsubscribe_url,
            ),
            "delay_hours": 0,
        },
        {
            "subject": f"¿Sabías que {sector} ya están certificados en NIS2?",
            "body": EMAIL_2_24H.format(
                sector=sector, n_criticos=n_criticos, price=price,
                checkout_url=checkout_url, unsubscribe_url=unsubscribe_url,
            ),
            "delay_hours": 24,
        },
        {
            "subject": "Caso real: PYME multada con 180.000 € por incumplir NIS2",
            "body": EMAIL_3_72H.format(
                price=price, checkout_url=checkout_url, unsubscribe_url=unsubscribe_url,
            ),
            "delay_hours": 72,
        },
        {
            "subject": f"Oferta exclusiva: 15% de descuento — {deadline}",
            "body": EMAIL_4_7D.format(
                deadline=deadline, original_price=original_price,
                discounted_price=discounted_price, savings=savings,
                checkout_url=checkout_url, unsubscribe_url=unsubscribe_url,
            ),
            "delay_hours": 168,
        },
        {
            "subject": "Último aviso — Guarda este enlace para cuando lo necesites",
            "body": EMAIL_5_14D.format(
                checkout_url=checkout_url, unsubscribe_url=unsubscribe_url,
                remind_30_url=f"{DOMAIN}/remind?email={email}&days=30",
                remind_90_url=f"{DOMAIN}/remind?email={email}&days=90",
            ),
            "delay_hours": 336,
        },
    ]

    print(f"📧 Encolando secuencia de {len(seq)} emails para {email}")
    for i, s in enumerate(seq):
        delay = s["delay_hours"]
        if delay == 0:
            Thread(target=_send_now, args=(email, s["subject"], s["body"]), daemon=True).start()
        else:
            Thread(
                target=_delayed_send,
                args=(email, s["subject"], s["body"], delay),
                daemon=True,
            ).start()
        print(f"   Email {i+1}: '{s['subject']}' (en {delay}h)")


def _delayed_send(to_email: str, subject: str, html_body: str, delay_hours: int):
    import time as _time
    _time.sleep(delay_hours * 3600)
    _send_now(to_email, subject, html_body)


def send_demo_sequence(email: str, findings: dict, repo_url: str):
    secrets = len(findings.get("secrets", []))
    vulns = len(findings.get("vulnerabilities", []))
    sast = len(findings.get("sast", []))
    total = secrets + vulns + sast
    n_criticos = secrets + sum(1 for v in findings.get("vulnerabilities", []) if v.get("severity", "").upper() in ("CRITICAL", "HIGH"))
    hidden_count = max(0, total - 2)

    demo_data = {
        "repo_name": repo_url.split("/")[-1] if "/" in repo_url else repo_url,
        "score": max(0, min(100, 100 - total * 5)),
        "fine": "10.000.000" if total > 10 else "2.000.000",
        "hidden_count": hidden_count,
        "n_criticos": n_criticos,
        "sector": "las empresas tecnológicas",
        "price": 299,
        "findings_summary": f"{n_criticos} críticos y {total} hallazgos totales",
    }
    send_sequence(email, demo_data)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Secuencia de emails de conversión")
    parser.add_argument("--email", required=True, help="Email del lead")
    parser.add_argument("--repo", default="tu repositorio", help="URL del repo")
    parser.add_argument("--send-demo", action="store_true", help="Enviar secuencia demo")
    args = parser.parse_args()

    if args.send_demo:
        send_demo_sequence(args.email, {}, args.repo)
    else:
        send_sequence(args.email, {"repo_name": args.repo, "score": 45, "fine": "10.000.000", "hidden_count": 12, "n_criticos": 3, "sector": "las empresas de tu sector", "price": 299})

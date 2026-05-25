#!/usr/bin/env python3
import argparse
import os
import smtplib
import ssl
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

EMAIL_USER = os.getenv("EMAIL_USER", "")
EMAIL_PASS = os.getenv("EMAIL_PASS", "")

SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))


def send_email(
    to_email: str,
    subject: str,
    html_body: str = "",
    attach_path: str | None = None,
    smtp_server: str = SMTP_SERVER,
    smtp_port: int = SMTP_PORT,
) -> bool:
    if not EMAIL_USER or not EMAIL_PASS:
        print(f"ℹ️  Modo simulado: email enviado a {to_email}")
        print(f"   Asunto: {subject}")
        if attach_path:
            print(f"   Adjunto: {attach_path}")
        print(f"   (Define EMAIL_USER y EMAIL_PASS para envío real)")
        return True

    msg = MIMEMultipart("mixed")
    msg["From"] = EMAIL_USER
    msg["To"] = to_email
    msg["Subject"] = subject

    body = html_body or f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: Arial, sans-serif; padding: 20px; background: #f4f4f4;">
<div style="max-width: 600px; margin: 0 auto; background: white; border-radius: 12px; padding: 30px;">
    <h2 style="color: #6366f1;">🛡️ CodeAudit Pro - Informe de Auditoría</h2>
    <p>Estimado cliente,</p>
    <p>Adjuntamos el informe ejecutivo de la auditoría de seguridad y calidad de su código.</p>
    <p>El informe incluye:</p>
    <ul>
        <li>🔒 Secretos y vulnerabilidades detectadas</li>
        <li>📊 Medición de deuda técnica</li>
        <li>📝 Recomendaciones priorizadas</li>
    </ul>
    <p>Si tiene alguna pregunta, no dude en responder a este correo.</p>
    <p style="margin-top: 30px; color: #94a3b8; font-size: 12px;">
        CodeAudit Pro · Auditoría de código para PYMES<br>
        Este es un mensaje automático.
    </p>
</div>
</body>
</html>"""

    msg.attach(MIMEText(body, "html", "utf-8"))

    if attach_path:
        path = Path(attach_path)
        if path.exists():
            with open(path, "rb") as f:
                part = MIMEApplication(f.read(), _subtype="html")
                part.add_header("Content-Disposition", f"attachment; filename={path.name}")
                msg.attach(part)

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls(context=context)
            server.login(EMAIL_USER, EMAIL_PASS)
            server.send_message(msg)
        print(f"✓ Email enviado a {to_email}")
        return True
    except Exception as e:
        print(f"❌ Error al enviar email: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Envío automático de informes por email")
    parser.add_argument("--to", required=True, help="Email del destinatario")
    parser.add_argument("--subject", default="Informe de Auditoría - CodeAudit Pro", help="Asunto del correo")
    parser.add_argument("--body", help="Ruta a archivo HTML con el cuerpo del mensaje")
    parser.add_argument("--attach", help="Ruta al archivo a adjuntar")

    args = parser.parse_args()

    html_body = ""
    if args.body:
        body_path = Path(args.body)
        if body_path.exists():
            html_body = body_path.read_text(encoding="utf-8")

    send_email(args.to, args.subject, html_body, args.attach)


if __name__ == "__main__":
    main()

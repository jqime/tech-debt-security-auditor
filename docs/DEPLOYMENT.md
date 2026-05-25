# Despliegue en Producción

Este documento describe cómo desplegar CodeAudit Pro en un VPS con Ubuntu 22.04+.

## Requisitos del Sistema

- Ubuntu 22.04 / Debian 12
- Python 3.10+
- Nginx
- Let's Encrypt (SSL)
- Git

## Paso 1: Instalar dependencias del sistema

```bash
apt update && apt upgrade -y
apt install -y python3 python3-pip python3-venv nginx git curl
```

## Paso 2: Clonar e instalar

```bash
git clone https://github.com/jqime/tech-debt-security-auditor /opt/codeaudit
cd /opt/codeaudit
python3 -m venv venv
source venv/bin/activate

# Herramientas de escaneo
pip install semgrep bandit truffleHog weasyprint qrcode[pil]

# Trivy
curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh | sh
```

## Paso 3: Configurar variables de entorno

```bash
cp .env.example .env
# Editar .env con los valores reales
nano .env
```

Variables requeridas:
- `STRIPE_SECRET_KEY` — Para pagos.
- `STRIPE_WEBHOOK_SECRET` — Webhook de Stripe.
- `EMAIL_USER` / `EMAIL_PASS` — Gmail app password.
- `GITHUB_TOKEN` — Para remediación automática.
- `SIEM_WEBHOOK_URL` / `SIEM_TOKEN` — Opcional, para SIEM.

## Paso 4: Systemd — Dashboard

```ini
# /etc/systemd/system/codeaudit-dashboard.service
[Unit]
Description=CodeAudit Pro Dashboard
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/codeaudit
EnvironmentFile=/opt/codeaudit/.env
ExecStart=/opt/codeaudit/venv/bin/python3 app/dashboard/app.py
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
systemctl daemon-reload
systemctl enable --now codeaudit-dashboard
```

## Paso 5: Systemd — Payment Server

```ini
# /etc/systemd/system/codeaudit-payment.service
[Unit]
Description=CodeAudit Pro Payment Server
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/codeaudit
EnvironmentFile=/opt/codeaudit/.env
ExecStart=/opt/codeaudit/venv/bin/python3 payment.py
Restart=always

[Install]
WantedBy=multi-user.target
```

## Paso 6: Systemd — Continuous Audit

```ini
# /etc/systemd/system/codeaudit-continuous.service
[Unit]
Description=CodeAudit Pro Continuous Audit
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/codeaudit
EnvironmentFile=/opt/codeaudit/.env
ExecStart=/opt/codeaudit/venv/bin/python3 continuous_audit.py --daemon
Restart=always

[Install]
WantedBy=multi-user.target
```

## Paso 7: Nginx + SSL

```nginx
# /etc/nginx/sites-available/codeaudit
server {
    listen 80;
    server_name codeauditpro.com *.codeauditpro.com;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /api/payment {
        proxy_pass http://127.0.0.1:5002;
    }

    location /webhook {
        proxy_pass http://127.0.0.1:5003;
    }
}
```

```bash
certbot --nginx -d codeauditpro.com -d *.codeauditpro.com
systemctl reload nginx
```

## Paso 8: Verificar

```bash
curl -I https://codeauditpro.com
curl https://codeauditpro.com/health
```

## Mantenimiento

```bash
# Actualizar código
cd /opt/codeaudit && git pull && systemctl restart codeaudit-dashboard

# Ver logs
journalctl -u codeaudit-dashboard -f
journalctl -u codeaudit-payment -f

# Backup base de datos
cp /opt/codeaudit/data/dashboard.db /opt/codeaudit/backups/dashboard-$(date +%F).db
```

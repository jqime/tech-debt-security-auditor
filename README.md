# 🛡️ CodeAudit Pro — Tech Debt & Security Auditor

[![GitHub Marketplace](https://img.shields.io/badge/Marketplace-CodeAudit%20Pro-blue?logo=github&style=flat-square)](https://github.com/marketplace)
[![CI](https://github.com/jqime/tech-debt-security-auditor/actions/workflows/example-codeaudit.yml/badge.svg)](https://github.com/jqime/tech-debt-security-auditor/actions)

Auditoría automatizada de seguridad y deuda técnica para PYMES. Genera informes ejecutivos HTML premium en 24h.

También disponible como **GitHub Action** — ejecuta auditorías automáticas en cada push o pull request.

---

## ✨ Funcionalidades Técnicas

- **🔒 Security Scan**: Secretos, API keys, tokens, dependencias vulnerables.
- **📊 Debt Measurement**: Complejidad ciclomática, líneas duplicadas, maintainability.
- **🎨 HTML Report**: Informe visual oscuro con métricas y recomendaciones.

---

## 🚀 Quick Start (Auditoría)

```bash
# Autenticar OpenCode (gratuito)
opencode auth login

# Auditar un repositorio
./run-audit.sh https://github.com/octocat/Hello-World

# El informe estará en:
# reports/executive-report.html
```

---

## 🔄 GitHub Action

Ejecuta auditorías automáticas en cada push o pull request:

```yaml
# .github/workflows/codeaudit.yml
name: CodeAudit Pro

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run CodeAudit Pro
        uses: jqime/tech-debt-security-auditor/.github/actions/codeaudit@main
        id: codeaudit
        with:
          comment_pr: 'true'
          github_token: ${{ secrets.GITHUB_TOKEN }}
      - uses: actions/upload-artifact@v4
        with:
          name: codeaudit-report
          path: reports/executive-report.html
```

**Inputs disponibles:**

| Input | Descripción | Default |
|-------|-------------|---------|
| `repo_url` | URL del repo a auditar (vacío = repo actual) | `''` |
| `opencode_model` | Modelo de OpenCode | `opencode/deepseek-v4-flash-free` |
| `comment_pr` | Comentar hallazgos en PR | `true` |
| `github_token` | Token para comentar en PRs | `''` |

**Outputs:** `secrets_count`, `vulnerabilities_count`, `report_path`

---

## 💼 Módulos de Negocio

### 1. Prospección de Clientes (`prospect.py`)

Busca empresas tecnológicas en un radio de 50 km de una ciudad:

```bash
# Con API key real (Google Maps):
export GOOGLE_MAPS_API_KEY=tu_api_key
python3 prospect.py Madrid

# Sin API key (usa datos simulados de ejemplo):
python3 prospect.py Barcelona
```

Los leads se guardan en `data/leads.csv`.

### 2. Landing Page (`app/landing/index.html`)

Página de marketing con Bootstrap 5. Ábrela directamente:

```bash
python3 -m http.server 8080 -d app/landing
# Abre http://localhost:8080
```

### 3. Pagos con Stripe (`payment.py`)

```bash
export STRIPE_SECRET_KEY=sk_test_...

# Crear productos en Stripe
python3 payment.py --setup

# Crear sesión de checkout
python3 payment.py --checkout auditoria_unica --repo https://github.com/user/repo --email cliente@email.com

# Procesar webhook
python3 payment.py --webhook webhook-event.json
```

### 4. Envío de Informes (`email_sender.py`)

```bash
export EMAIL_USER=tu.correo@gmail.com
export EMAIL_PASS=contraseña_app

python3 email_sender.py \
  --to cliente@email.com \
  --subject "Informe de auditoría" \
  --attach reports/executive-report.html
```

### 5. Dashboard de Gestión (`app/dashboard/app.py`)

Panel Flask con autenticación, estadísticas y control de auditorías:

```bash
export DASHBOARD_USER=admin
export DASHBOARD_PASS=cambiar123

pip install flask
python3 app/dashboard/app.py
# Abre http://localhost:5000
```

### 6. Cola de Tareas Automatizada (`runner.py`)

```bash
# Añadir tarea
python3 runner.py --add https://github.com/user/repo --email cliente@email.com

# Procesar una vez
python3 runner.py --run-once

# Ejecutar como daemon (revisa cada 30s)
python3 runner.py --daemon

# Listar tareas
python3 runner.py --list
python3 runner.py --list pending
```

---

## 🔄 Flujo Completo (Cliente Simulado)

```bash
# 1. Generar leads
python3 prospect.py Madrid

# 2. Añadir tarea de auditoría
python3 runner.py --add https://github.com/octocat/Hello-World --email cliente@ejemplo.com

# 3. Procesar la tarea (ejecuta auditoría + envía email)
python3 runner.py --run-once

# 4. Ver el dashboard
python3 app/dashboard/app.py
# Abre http://localhost:5000 (user: admin / pass: admin123)

# 5. Ver los informes generados
ls reports/
```

---

## ⚙️ Variables de Entorno

| Variable | Descripción |
|----------|-------------|
| `GOOGLE_MAPS_API_KEY` | API key de Google Maps (prospección) |
| `STRIPE_SECRET_KEY` | Secret key de Stripe (pagos) |
| `EMAIL_USER` | Correo Gmail para envío de informes |
| `EMAIL_PASS` | Contraseña de aplicación de Gmail |
| `SMTP_SERVER` | Servidor SMTP (por defecto smtp.gmail.com) |
| `SMTP_PORT` | Puerto SMTP (por defecto 587) |
| `DASHBOARD_USER` | Usuario del panel (por defecto admin) |
| `DASHBOARD_PASS` | Contraseña del panel (por defecto admin123) |
| `DASHBOARD_PORT` | Puerto del dashboard (por defecto 5000) |
| `RUNNER_INTERVAL` | Intervalo del daemon en segundos (por defecto 30) |

---

## 📝 Blog Técnico

Artículos sobre seguridad, calidad de código, automatización y negocio:

- [OpenCode CLI vs. Antigravity para Automatización en 2026](app/blog/opencode-vs-antigravity/) — Comparativa técnica, benchmarks y casos de uso.
- [SEO para Herramientas de Desarrollador: Guía Completa 2026](app/blog/seo-guide-2026/) — Schema markup, topic clusters y AI Overviews.
- [Auditoría de Código Automática con OpenCode: Caso Práctico](app/blog/code-audit-case-study/) — Cómo una PYME evitó 10.000 € en pérdidas.

→ [Ver todos los artículos](app/blog/index.html)

---

## 📁 Estructura del Proyecto

```
tech-debt-security-auditor/
├── run-audit.sh              # 🚀 Script maestro de auditoría
├── runner.py                 # Cola de tareas
├── email_sender.py           # Envío de emails
├── payment.py                # Integración Stripe
├── prospect.py               # Prospección de clientes
├── engine/                   # ⚙️ Motor de auditoría
│   ├── run.sh                # Orquestador Python
│   └── generate_report.py    # Generador HTML
├── app/                      # 🖥️ Aplicación web
│   ├── dashboard/app.py      # Panel Flask
│   ├── landing/index.html    # Landing page marketing
│   └── blog/                 # Blog técnico
│       ├── index.html
│       ├── opencode-vs-antigravity/
│       ├── seo-guide-2026/
│       └── code-audit-case-study/
├── .github/                  # 🔄 GitHub Actions
│   ├── actions/codeaudit/    # Acción personalizada
│   └── workflows/            # Workflows de ejemplo
├── docs/                     # 📚 Documentación
│   └── BUSINESS_PLAN.md
├── tools/                    # 🛠️ Utilidades
│   └── publish_blog.sh
├── data/                     # 📊 Datos de ejecución
│   ├── leads.csv
│   └── tasks.json
├── reports/                  # 📈 Informes generados
│   ├── security-report.json
│   ├── debt-report.json
│   └── executive-report.html
├── skills/                   # 🧠 OpenCode skills
└── tests/                    # ✅ Tests
```

---

## 📄 BUSINESS PLAN

Ver `BUSINESS_PLAN.md` para estrategia completa de precios, márgenes y adquisición de clientes.

---

## 🚀 Despliegue en Producción (VPS)

### Requisitos mínimos

- VPS con 1 CPU, 1 GB RAM, 20 GB SSD (DigitalOcean $6/mo, Hetzner $4/mo)
- Ubuntu 22.04+ / Debian 12+
- Dominio apuntando al VPS (opcional pero recomendado)

### 1. Clonar el repositorio

```bash
git clone https://github.com/jqime/tech-debt-security-auditor.git
cd tech-debt-security-auditor
```

### 2. Configurar variables de entorno

```bash
export STRIPE_SECRET_KEY="sk_test_..."          # Stripe (modo test)
export STRIPE_WEBHOOK_SECRET="whsec_..."         # Stripe webhook secret
export EMAIL_USER="tuemail@gmail.com"            # Gmail
export EMAIL_PASS="contraseña_aplicacion"        # App password de Gmail
export DASHBOARD_USER="admin"                    # Admin dashboard
export DASHBOARD_PASS="contraseña_segura"        # Cambiar en producción
export DASHBOARD_SECRET="clave_secreta_aleatoria" # Flask session key
export DOMAIN="https://tudominio.com"             # Para redirects Stripe
```

Para variables persistentes, crea un archivo `.env`:

```bash
cat > .env << EOF
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
EMAIL_USER=tuemail@gmail.com
EMAIL_PASS=contraseña_aplicacion
DASHBOARD_USER=admin
DASHBOARD_PASS=cambiar123
DASHBOARD_SECRET=$(openssl rand -hex 32)
DOMAIN=https://tudominio.com
EOF
```

### 3. Ejecutar deploy automático

```bash
chmod +x deploy.sh
./deploy.sh
```

Esto instala dependencias, arranca los 4 servicios y los deja corriendo.

### 4. Proxy inverso con nginx (recomendado)

```nginx
server {
    listen 80;
    server_name tudominio.com;

    location / {
        proxy_pass http://127.0.0.1:5000;  # Dashboard
        proxy_set_header Host $host;
    }

    location /submit-lead {
        proxy_pass http://127.0.0.1:5001;  # Landing handler
    }

    location /create-checkout-session {
        proxy_pass http://127.0.0.1:5002;  # Payment
    }

    location /stripe-webhook {
        proxy_pass http://127.0.0.1:5002;
    }
}
```

### 5. Systemd services (producción)

Crea `/etc/systemd/system/codeaudit-*.service` para cada servicio:

```bash
# Ejemplo: /etc/systemd/system/codeaudit-dashboard.service
[Unit]
Description=CodeAudit Pro Dashboard
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/tech-debt-security-auditor
EnvironmentFile=/opt/tech-debt-security-auditor/.env
ExecStart=/usr/bin/python3 app/dashboard/app.py
Restart=always

[Install]
WantedBy=multi-user.target
```

### 6. Estructura de puertos

| Servicio | Puerto | Descripción |
|----------|--------|-------------|
| Dashboard | 5000 | Panel web multi-usuario |
| Landing handler | 5001 | Formulario de leads |
| Payment | 5002 | Stripe checkout + webhooks |
| Runner (daemon) | — | Cola de tareas automática |

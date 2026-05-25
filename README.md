# 🛡️ CodeAudit Pro — Tech Debt & Security Auditor

Auditoría automatizada de seguridad y deuda técnica para PYMES. Genera informes ejecutivos HTML premium en 24h.

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

### 2. Landing Page (`landing/index.html`)

Página de marketing con Bootstrap 5. Ábrela directamente:

```bash
python3 -m http.server 8080 -d landing
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

### 5. Dashboard de Gestión (`dashboard/app.py`)

Panel Flask con autenticación, estadísticas y control de auditorías:

```bash
export DASHBOARD_USER=admin
export DASHBOARD_PASS=cambiar123

pip install flask
python3 dashboard/app.py
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
python3 dashboard/app.py
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

- [OpenCode CLI vs. Antigravity para Automatización en 2026](blog/opencode-vs-antigravity/) — Comparativa técnica, benchmarks y casos de uso.
- [SEO para Herramientas de Desarrollador: Guía Completa 2026](blog/seo-guide-2026/) — Schema markup, topic clusters y AI Overviews.
- [Auditoría de Código Automática con OpenCode: Caso Práctico](blog/code-audit-case-study/) — Cómo una PYME evitó 10.000 € en pérdidas.

→ [Ver todos los artículos](blog/index.html)

---

## 📁 Estructura del Proyecto

```
tech-debt-security-auditor/
├── run-audit.sh              # Script maestro de auditoría
├── scripts/
│   ├── run.sh                 # Orquestador Python
│   └── generate_report.py     # Generador HTML
├── prospect.py                # Prospección de clientes
├── payment.py                 # Integración Stripe
├── email_sender.py            # Envío de emails
├── runner.py                  # Cola de tareas
├── landing/index.html         # Landing page marketing
├── dashboard/app.py           # Panel Flask
├── business-plan.md           # Plan de negocio
├── blog/
│   ├── index.html             # Listado de artículos
│   ├── opencode-vs-antigravity/   # Artículo 1
│   ├── seo-guide-2026/            # Artículo 2
│   └── code-audit-case-study/     # Artículo 3
├── tools/
│   └── publish_blog.sh        # Script de publicación
├── data/
│   ├── leads.csv              # Leads generados
│   └── tasks.json             # Cola de tareas
└── reports/
    ├── security-report.json
    ├── debt-report.json
    └── executive-report.html
```

---

## 📄 BUSINESS PLAN

Ver `BUSINESS_PLAN.md` para estrategia completa de precios, márgenes y adquisición de clientes.

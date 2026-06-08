# CodeAudit Pro

**Plataforma DevSecOps SaaS — Auditoría de seguridad, deuda técnica y cumplimiento normativo NIS2/DORA**

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white">
  <img src="https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white">
  <img src="https://img.shields.io/badge/Flask-2.3-000000?logo=flask&logoColor=white">
  <img src="https://img.shields.io/badge/Stripe-Payments-635BFF?logo=stripe&logoColor=white">
  <img src="https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white">
  <br>
  <img src="https://img.shields.io/badge/Trivy-0.70-red?logo=trivy">
  <img src="https://img.shields.io/badge/Semgrep-1.63-6a0dad">
  <img src="https://img.shields.io/badge/Bandit-1.7-FF6600">
  <img src="https://img.shields.io/badge/License-MIT-yellow">
</p>

---

## Tabla de Contenidos

- [Descripción General](#descripción-general)
- [Arquitectura](#arquitectura)
- [Características](#características)
- [Inicio Rápido](#inicio-rápido)
- [Uso](#uso)
- [Variables de Entorno](#variables-de-entorno)
- [Planes y Precios](#planes-y-precios)
- [Estructura del Proyecto](#estructura-del-proyecto)
- [Despliegue](#despliegue)
- [Desarrollo](#desarrollo)

---

## Descripción General

CodeAudit Pro automatiza el ciclo completo de seguridad y compliance para PYMES tecnológicas y empresas del sector financiero. Combina **5 escáneres de clase empresarial** (Trivy, Semgrep, Bandit, truffleHog, Lizard/Radon) con un **motor de cumplimiento normativo** que mapea hallazgos contra **NIS2** (Art. 21/23) y **DORA** (Art. 5–16), y genera informes ejecutivos certificados con SHA-256 + QR.

El producto está diseñado para maximizar la conversión mediante un **embudo de ventas automatizado**:
- Demo en vivo con **FOMO paywall** — el usuario ve sus vulnerabilidades pero paga para desbloquear la remediación
- **Prospección autónoma** sobre repositorios públicos GitHub + campaña de email regulatorio (5 emails, secuencia NIS2/DORA)
- **Recuperación de carritos abandonados** con descuento del 10% vía Stripe + email
- **Certificación blockchain** para validez legal ante auditores externos

---

## Arquitectura

```
                   ┌─────────────────┐
                   │   Nginx (SSL)   │  ← Rate limiting, HSTS, CSP
                   └────────┬────────┘
                            │
              ┌─────────────┼─────────────┐
              │             │             │
        ┌─────▼────┐ ┌─────▼────┐ ┌─────▼────┐
        │Dashboard │ │  Landing │ │ Payments │
        │ :5000    │ │ :5001    │ │ :5002    │
        │ Gunicorn │ │ Gunicorn │ │ Gunicorn │
        └─────┬────┘ └─────┬────┘ └─────┬────┘
              │             │             │
              └─────────────┼─────────────┘
                            │
                    ┌───────▼───────┐
                    │  PostgreSQL   │
                    │  (o SQLite)   │
                    └───────────────┘

    ┌──────────────────┐    ┌──────────────────┐
    │ Continuous Audit │    │     Runner       │
    │ :5003            │    │  (worker daemon) │
    │ Webhooks + cron  │    │  Cola + SIEM     │
    └──────────────────┘    └──────────────────┘
```

| Servicio | Puerto | Tecnología | Responsabilidad |
|---|---|---|---|
| **Dashboard** | `5000` | Flask + Gunicorn | Panel ejecutivo, KPIs, login, informes |
| **Landing** | `5001` | Flask + Gunicorn | Página de marketing, demo interactiva, FOMO paywall |
| **Payments** | `5002` | Flask + Gunicorn | Stripe Checkout, webhooks, carritos abandonados |
| **Continuous Audit** | `5003` | Flask (Werkzeug) | Webhooks GitHub, auditoría programada |
| **Runner** | — | Python (daemon) | Orquestador de escáneres, cola con Semaphore(3), integraciones SIEM/Jira |

---

## Características

### Seguridad y Escaneo
- **Trivy** — Vulnerabilidades en dependencias (OS-level, pip, npm)
- **Semgrep** — SAST multi-lenguaje con reglas personalizadas OWASP
- **Bandit** — SAST especializado Python
- **truffleHog** — Detección de secretos por regex + entropía
- **Lizard / Radon** — Complejidad ciclomática y deuda técnica

### Cumplimiento Normativo
- **NIS2** — Mapeo contra Art. 21 (seguridad redes, criptografía, control acceso) y Art. 23 (notificación incidentes)
- **DORA** — Mapeo contra Art. 5–16 (gestión riesgo TIC), Art. 17–23 (notificación), Art. 24–29 (resiliencia, terceros)
- Informe **HTML + PDF** con declaración de debida diligencia para auditores externos
- Certificación **SHA-256 + QR** con verificación móvil

### Motor de Ventas y CRO
- **Demo en vivo** — Escanea cualquier repositorio público en tiempo real con SSE
- **FOMO Paywall** — Muestra todos los hallazgos con blur selectivo; el usuario ve la estructura pero paga para desbloquear valores exactos
- **Prospección GitHub** — Busca repositorios por topic (fintech, cloud-security, banking-api), extrae emails de commits y lanza campaña de 5 emails con urgencia regulatoria
- **Recuperación de carritos** — Detecta demos sin pago tras 2h y envía email con 10% de descuento
- **Precios dinámicos** — 299 € / 1.500 € según volumen de hallazgos

### Integraciones
- **Stripe** — Checkout Session, webhooks, suscripciones, idempotencia
- **SIEM** — Splunk HEC, Elasticsearch, webhook genérico (formato CEF-like)
- **Jira** — Creación automática de issues por hallazgo crítico
- **GitHub Webhooks** — HMAC validation (SHA1 + SHA256), auditoría continua en push/PR
- **Email** — Secuencia de 5 correos con plantillas NIS2/DORA

### Seguridad Perimetral
- **HMAC** dual en webhooks GitHub
- **Multi-tenencia** por tabla `report_registry` + verificación por `user_id`
- **Rate limiting**, **HSTS**, **CSP** en Nginx
- **Cifrado .env** con AES-256-CBC + systemd `LoadCredential`
- **Idempotencia** en Stripe y escrituras atómicas en `hashes.log`

---

## Inicio Rápido

### Con Docker Compose (recomendado)

```bash
# 1. Clonar
git clone https://github.com/jqime/tech-debt-security-auditor.git
cd tech-debt-security-auditor

# 2. Configurar variables de entorno
cp .env.example .env
nano .env

# 3. Levantar todo
docker compose up -d --build

# 4. Verificar
curl http://localhost:5000          # Dashboard
curl http://localhost:5001/health   # Landing
curl http://localhost:5002/health   # Payments
curl http://localhost:5003/status   # Continuous Audit
```

### Sin Docker (desarrollo)

```bash
# 1. Dependencias del sistema
sudo apt install python3 python3-pip git nginx

# 2. Dependencias Python
pip install -r requirements.txt
pip install semgrep bandit truffleHog weasyprint qrcode[pil]

# 3. Trivy
curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh | sh

# 4. Auditoría de prueba
./run_audit.sh https://github.com/octocat/Hello-World
./test_compliance.sh
```

---

## Uso

### Auditoría desde CLI

```bash
# Auditoría completa
./run_audit.sh https://github.com/tu-empresa/tu-repo

# Solo compliance
python3 compliance_report.py

# Certificar informe existente
python3 certify.py --certify

# Pipeline completo
./test_compliance.sh
```

### Demo interactiva

```bash
# La landing expone la demo en vivo
# Abrir en navegador: http://localhost:5001
# Introducir URL de repositorio público → escaneo SSE → FOMO paywall
```

### Prospección de leads

```bash
# Buscar repositorios fintech en GitHub y lanzar campaña de email
export GITHUB_TOKEN="ghp_tu_token"
python3 prospect.py --topic fintech --limit 20 --drip
```

### Auditoría continua

```bash
python3 continuous_audit.py --daemon
# Webhook: POST http://localhost:5003/webhook/github
```

---

## Variables de Entomio

| Variable | Obligatorio | Descripción |
|---|---|---|
| `STRIPE_SECRET_KEY` | Pagos | Secret key de Stripe (test o live) |
| `STRIPE_WEBHOOK_SECRET` | Pagos | Firma de webhook Stripe |
| `EMAIL_USER` | Email campañas | Correo Gmail para envíos |
| `EMAIL_PASS` | Email campañas | Contraseña de aplicación Gmail |
| `GITHUB_TOKEN` | Prospección / remediación | Token GitHub con scopes `repo`, `read:user` |
| `BASE_URL` | General | URL base (ej: `https://codeauditpro.com` o `http://localhost:5000`) |
| `DASHBOARD_USER` | Opcional | Usuario admin (defecto: `admin`) |
| `DASHBOARD_PASS` | Opcional | Contraseña admin |
| `DASHBOARD_PORT` | Opcional | Puerto dashboard (defecto: `5000`) |
| `PAYMENT_PORT` | Opcional | Puerto payments (defecto: `5002`) |
| `CONTINUOUS_PORT` | Opcional | Puerto continuous audit (defecto: `5003`) |
| `LANDING_PORT` | Opcional | Puerto landing (defecto: `5001`) |
| `ENGINE_TIMEOUT` | Opcional | Timeout del motor de escaneo en segundos (defecto: `1800`) |
| `SIEM_WEBHOOK_URL` | Opcional | URL del webhook SIEM (Splunk/ELK) |
| `SIEM_TOKEN` | Opcional | Token de autenticación SIEM |
| `JIRA_URL` | Opcional | URL de instancia Jira |
| `JIRA_EMAIL` | Opcional | Email de usuario Jira |
| `JIRA_TOKEN` | Opcional | Token de API Jira |
| `GITHUB_WEBHOOK_SECRET` | Opcional | Secreto para verificar webhooks GitHub |

---

## Planes y Precios

| Plan | Precio | Repos | Características |
|---|---|---|---|
| **Gratuito** | 0 € | 1 público | Escaneo básico + resumen ejecutivo |
| **Pro** | 299 € / auditoría | 1 privado/público | Informe completo + dashboard + email |
| **Compliance Pro** | 1.500 € / auditoría | 1 | NIS2/DORA + PDF certificado + blockchain |
| **Professional** | 9.900 € / año | Hasta 10 | Informes mensuales + remediación básica |
| **Enterprise** | 29.900 € / año | Hasta 50 | White-label + SIEM + soporte 24/7 + continua |
| **Custom** | Bajo demanda | >100 | On-premise + SLA dedicado + consultoría |

---

## Estructura del Proyecto

```
tech-debt-security-auditor/
│
├── docker-compose.yml          # Orquestación Docker (6 servicios)
├── Dockerfile                  # Imagen base Python 3.11 + Trivy
├── requirements.txt            # Dependencias Python
│
├── app/                        # Aplicaciones web
│   ├── dashboard/app.py        # Dashboard ejecutivo (Flask + Gunicorn)
│   ├── demo/demo.py            # Demo SSE en vivo + FOMO paywall
│   ├── landing/index.html      # Página de marketing
│   ├── whitelabel/             # Portal white-label
│   ├── db.py                   # Capa de base de datos SQLite
│   └── blog/                   # Blog técnico
│
├── engine/                     # Motor de auditoría
│   ├── run.py                  # Orquestador de escáneres (Trivy, Semgrep, Bandit, truffleHog, Lizard, Radon)
│   └── generate_report.py      # Generador de informes HTML + PDF
│
├── deploy/                     # Despliegue en producción
│   ├── production_deploy.sh    # Script maestro de despliegue
│   ├── codeauditpro.nginx      # Configuración Nginx (HSTS, CSP, rate limiting)
│   ├── codeaudit-dashboard.service
│   ├── codeaudit-landing.service
│   ├── codeaudit-payments.service
│   └── codeaudit-continuous.service
│
├── integrations/               # Conectores externos
│   ├── siem.py                 # Splunk HEC / Elasticsearch / webhook genérico
│   └── jira.py                 # Jira Cloud API
│
├── runner.py                   # Cola de tareas con Semaphore(3) + SIEM/Jira
├── continuous_audit.py         # Webhooks GitHub + scheduler APScheduler
├── payment.py                  # Stripe Checkout + webhooks + carritos abandonados
├── landing_handler.py          # Backend API de la landing page
├── prospect.py                 # Scraper GitHub + campaña de email drip
├── certify.py                  # Certificación SHA-256 + QR + OpenTimestamps
├── compliance_report.py        # Informe NIS2/DORA HTML + PDF
├── auto_remediate.py           # PRs/issues automáticos en GitHub
├── email_sender.py             # Envío de emails transaccionales
├── email_sequences.py          # Secuencia de 5 emails NIS2/DORA
│
├── run_audit.sh                # Script maestro de auditoría CLI
├── test_compliance.sh          # Pipeline de prueba (auditoría → compliance → certificación)
├── deploy.sh                   # Alias para test rápido
│
├── data/                       # Datos de ejecución (leads, logs)
├── reports/                    # Informes generados (HTML, PDF, hashes)
├── docs/                       # Documentación adicional
├── .github/                    # GitHub Actions CI/CD
│
├── README.md                   # Este archivo
├── CHANGELOG.md                # Historial de versiones
├── CONTRIBUTING.md             # Guía de contribución
└── LICENSE                     # MIT License
```

---

## Despliegue

### Producción (VPS)

```bash
# 1. Configurar DNS apuntando a la IP del servidor
# 2. Preparar .env con claves reales
# 3. Ejecutar despliegue
sudo bash deploy/production_deploy.sh
```

El script:
- Instala dependencias (Python, Nginx, Certbot)
- Copia el código a `/opt/codeauditpro`
- Cifra `.env` con AES-256-CBC
- Configura systemd (4 unidades) + Nginx (rate limiting, HSTS, CSP)
- Solicita certificado SSL Let's Encrypt
- Arranca todos los servicios

### Staging (Docker Compose)

```bash
docker compose down
docker compose up -d --build
```

### Servicios post-despliegue

| Servicio | systemd | Puerto | Logs |
|---|---|---|---|
| Dashboard | `codeaudit-dashboard` | `5000` | `journalctl -u codeaudit-dashboard -f` |
| Landing | `codeaudit-landing` | `5001` | `journalctl -u codeaudit-landing -f` |
| Payments | `codeaudit-payments` | `5002` | `journalctl -u codeaudit-payments -f` |
| Continuous | `codeaudit-continuous` | `5003` | `journalctl -u codeaudit-continuous -f` |

---

## Desarrollo

### Requisitos
- Python 3.11+
- Docker Compose (opcional)
- Trivy, Semgrep, Bandit, truffleHog

### Entorno local

```bash
cp .env.example .env
# Editar .env con valores de prueba
pip install -r requirements.txt
python3 app/dashboard/app.py &     # Puerto 5000
python3 landing_handler.py &       # Puerto 5001
python3 payment.py &               # Puerto 5002
python3 continuous_audit.py --daemon &  # Puerto 5003
```

### Tests

```bash
# Pipeline completo de compliance
bash test_compliance.sh

# Verificación sintáctica
python3 -m py_compile app/dashboard/app.py
python3 -m py_compile payment.py
python3 -m py_compile prospect.py
```

### Convenciones
- **Python 3.11+** tipado opcional, estilo PEP 8
- **Flask** para servicios web, **Gunicorn** en producción
- **SQLite** con `Semaphore(3)` para concurrencia / **PostgreSQL** en Docker
- Logs estructurados con `print()` + timestamp
- `try/except` en todos los escáneres para tolerancia a fallos
- Commits convencionales: `feat:`, `fix:`, `docs:`, `chore:`

---

<p align="center">
  <b>CodeAudit Pro</b> — Cumplimiento NIS2/DORA para PYMES tecnológicas<br>
  <a href="https://github.com/jqime/tech-debt-security-auditor">GitHub</a> ·
  <a href="docs/API.md">API Docs</a> ·
  <a href="docs/DEPLOYMENT.md">Deployment Guide</a> ·
  <a href="docs/business_plan.md">Business Plan</a>
  <br>
  MIT © 2026 CodeAudit Pro
</p>

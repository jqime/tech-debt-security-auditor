# 🛡️ CodeAudit Pro

**Auditoría de seguridad, calidad y cumplimiento normativo NIS2/DORA para PYMES y empresas.**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](https://python.org)
[![GitHub Actions](https://github.com/jqime/tech-debt-security-auditor/actions/workflows/example-codeaudit.yml/badge.svg)](https://github.com/jqime/tech-debt-security-auditor/actions)
[![Trivy](https://img.shields.io/badge/Trivy-0.70-red)](https://trivy.dev)
[![Semgrep](https://img.shields.io/badge/Semgrep-1.63-6a0dad)](https://semgrep.dev)

---

## Descripción

CodeAudit Pro es una plataforma **DevSecOps** que automatiza la detección de vulnerabilidades, secretos expuestos, deuda técnica y el mapeo de hallazgos contra los marcos regulatorios **NIS2** y **DORA**. Genera informes ejecutivos en HTML y PDF, certifica su integridad mediante SHA-256 + QR, y puede enviar los hallazgos a **SIEM**, crear **PRs automáticos** en GitHub y auditar de forma continua mediante **webhooks**.

> **Precio desde:** 299 €/auditoría única · **Enterprise:** 29.900 €/año

---

## Tabla de Contenidos

- [Requisitos](#requisitos)
- [Instalación Rápida](#instalación-rápida)
- [Uso](#uso)
- [Variables de Entorno](#variables-de-entorno)
- [Módulos](#módulos)
- [Planes y Precios](#planes-y-precios)
- [Estructura del Proyecto](#estructura-del-proyecto)
- [Despliegue](#despliegue)
- [Contribuir](#contribuir)
- [Licencia](#licencia)

---

## Requisitos

### Sistema
- **Python** 3.10 o superior
- **Git**
- **Nginx** (para producción)

### Herramientas de escaneo (instalación automática vía pip)
| Herramienta | Propósito | Instalación |
|------------|-----------|-------------|
| [Trivy](https://trivy.dev) | Vulnerabilidades en dependencias | `curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh \| sh` |
| [Semgrep](https://semgrep.dev) | SAST multi-lenguaje | `pip install semgrep` |
| [Bandit](https://bandit.readthedocs.io) | SAST Python | `pip install bandit` |
| [truffleHog](https://github.com/trufflesecurity/trufflehog) | Secretos | `pip install truffleHog` |
| [WeasyPrint](https://weasyprint.org) | Generación PDF | `pip install weasyprint` |
| [QR Code](https://pypi.org/project/qrcode/) | QR de verificación | `pip install qrcode[pil]` |

---

## Instalación Rápida

```bash
# 1. Clonar
git clone https://github.com/jqime/tech-debt-security-auditor.git
cd tech-debt-security-auditor

# 2. Instalar dependencias Python
pip install -r requirements.txt

# 3. Instalar herramientas de escaneo
pip install semgrep bandit truffleHog weasyprint qrcode[pil]

# 4. Instalar Trivy (Linux)
curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh | sh

# 5. Dar permisos
chmod +x run_audit.sh deploy.sh test_compliance.sh

# 6. ¡Listo!
./run_audit.sh https://github.com/octocat/Hello-World
```

---

## Uso

### Auditoría básica
```bash
./run_audit.sh https://github.com/tu-empresa/tu-repo
```
Genera en `reports/`:
- `executive-report.html` — Informe ejecutivo premium
- `security-report.json` — Hallazgos de seguridad (Trivy + Semgrep + Bandit + truffleHog)
- `debt-report.json` — Métricas de deuda técnica

### Compliance NIS2/DORA
```bash
python3 compliance_report.py
```
Genera en `reports/`:
- `compliance-nis2.html` — Informe de cumplimiento normativo completo
- `compliance-nis2.pdf` — Versión PDF para auditores externos

### Certificación blockchain
```bash
python3 certify.py --certify
```
- Inserta bloque SHA-256 en el informe HTML
- Genera código QR de verificación
- Registra hash en `reports/hashes.log`

### Pipeline completo
```bash
./test_compliance.sh
```
Ejecuta: auditoría → compliance → certificación → resumen.

### Remediación automática
```bash
export GITHUB_TOKEN=ghp_xxxx
python3 auto_remediate.py --repo https://github.com/tu-empresa/tu-repo
```
Crea PRs automáticos con fixes de dependencias e issues para secretos.

### Auditoría continua
```bash
python3 continuous_audit.py --daemon
```
- Escucha webhooks de GitHub en `:5003/webhook/github`
- Auditorías programadas (diarias/semanales)
- Notificación por email si el score de compliance empeora

---

## Variables de Entorno

| Variable | Obligatorio | Descripción |
|----------|-------------|-------------|
| `STRIPE_SECRET_KEY` | Para pagos | Secret key de Stripe |
| `STRIPE_WEBHOOK_SECRET` | Para webhook | Firma de webhook Stripe |
| `EMAIL_USER` | Para emails | Correo Gmail |
| `EMAIL_PASS` | Para emails | Contraseña de aplicación Gmail |
| `GITHUB_TOKEN` | Para remediación | Token GitHub con permisos repo e issues |
| `SIEM_WEBHOOK_URL` | Opcional | URL del webhook SIEM (Splunk/ELK) |
| `SIEM_TOKEN` | Opcional | Token de autenticación SIEM |
| `DASHBOARD_USER` | Opcional | Usuario admin (defecto: admin) |
| `DASHBOARD_PASS` | Opcional | Contraseña admin (defecto: admin123) |
| `DASHBOARD_PORT` | Opcional | Puerto dashboard (defecto: 5000) |
| `PAYMENT_PORT` | Opcional | Puerto payment (defecto: 5002) |
| `CONTINUOUS_PORT` | Opcional | Puerto continuous audit (defecto: 5003) |

---

## Módulos

### 🖥️ Dashboard Ejecutivo
Panel web en Flask con login, KPIs en tiempo real, gráficos Chart.js:
- **Dashboard**: leads, auditorías, ingresos, últimas ejecuciones.
- **Cumplimiento**: radar NIS2/DORA, evolución temporal, desglose por artículo.
- **Cumplimiento Continuo**: score en el tiempo, vulnerabilidades críticas por repo, MTTR, alertas.
- **Mi Empresa**: personalización white-label (colores, logo).
- **Pagos**: historial de transacciones Stripe.

### 📋 Compliance NIS2/DORA
Mapeo automático de hallazgos de seguridad contra:
- **NIS2**: Art. 21 (seguridad redes, riesgo, continuidad, cadena suministro, criptografía, control acceso) y Art. 23 (notificación incidentes).
- **DORA**: Art. 5-16 (gestión riesgo TIC), Art. 17-23 (notificación), Art. 24 (resiliencia), Art. 25-29 (terceros), Art. 30 (intercambio información).
- Genera **HTML + PDF** con declaración de debida diligencia válida para auditores externos.

### 🔏 Certificación Blockchain
Cada informe recibe:
- **SHA-256** del contenido completo
- **Código QR** para verificación móvil
- **Hash log** con fecha y hora
- Compatible con **OpenTimestamps** (opcional)

### 🔄 Integración SIEM
Envía hallazgos críticos a:
- **Splunk HEC** (HTTP Event Collector)
- **Elasticsearch** / Kibana
- **Webhook genérico** (formato CEF-like)
- Simulación cuando no hay SIEM configurado.

### 🤖 Remediación Automática
- **PRs automáticos** en GitHub para vulnerabilidades de dependencias (actualiza package.json/requirements.txt).
- **Issues** para secretos expuestos con instrucciones de rotación.
- Modo `--dry-run` para simular sin riesgo.

### 🏢 Portal White-Label
- Personalización de colores, logo y nombre de empresa.
- Subdominio dedicado (`cliente.codeauditpro.com`).
- Configuración desde el dashboard ("Mi Empresa").

### ⏱️ Auditoría Continua
- **Webhooks** GitHub (push, pull_request) → auditoría automática.
- **Programación** diaria/semanal con APScheduler.
- **Alertas** por email si el score de compliance cae >10 puntos.

---

## Planes y Precios

| Plan | Precio | Repos | Características |
|------|--------|-------|-----------------|
| **Gratuito** | 0 € | 1 público | Escaneo básico, resumen ejecutivo |
| **Pro** | 299 €/aud | 1 | Informe completo, dashboard, email |
| **Compliance Pro** | 1.500 €/aud | 1 | NIS2/DORA, PDF, certificación blockchain |
| **Professional** | 9.900 €/año | Hasta 10 | Informes mensuales, remediación básica |
| **Enterprise** | 29.900 €/año | Hasta 50 | White-label, SIEM, soporte 24/7, continua |
| **Custom** | Bajo demanda | >100 | On-premise, SLA dedicado, consultoría |

---

## Estructura del Proyecto

```
tech-debt-security-auditor/
├── run_audit.sh              # 🚀 Script maestro de auditoría
├── runner.py                 # Cola de tareas + email ventas
├── compliance_report.py      # 📋 Informe NIS2/DORA + PDF
├── certify.py                # 🔏 Certificación blockchain
├── auto_remediate.py          # 🤖 PRs/issues automáticos
├── continuous_audit.py        # ⏱️ Webhooks + scheduler
├── email_sender.py            # Envío de emails
├── payment.py                 # Integración Stripe
├── prospect.py                # Prospección de clientes
├── landing_handler.py         # Backend landing page
├── enterprise_selling.md      # Guía de ventas enterprise
├── engine/                    # ⚙️ Motor de auditoría
│   ├── run.py                 # Orquestador (Trivy, Semgrep, Bandit, truffleHog)
│   └── generate_report.py     # Generador HTML
├── app/                       # 🖥️ Aplicación web
│   ├── dashboard/app.py       # Panel Flask + white-label
│   ├── landing/index.html     # Landing page marketing
│   ├── whitelabel/            # Portal white-label
│   └── blog/                  # Blog técnico
├── integrations/              # 🔗 Integraciones
│   ├── jira.py                # Jira Cloud
│   └── siem.py                # Splunk / ELK
├── .github/                   # 🔄 GitHub Actions
├── docs/                      # 📚 Documentación
│   ├── DEPLOYMENT.md          # Despliegue en producción
│   ├── API.md                 # Endpoints públicos
│   └── business_plan.md       # Plan de negocio
├── tools/                     # 🛠️ Utilidades
│   ├── migrate_enterprise.sh  # Demo + sandbox enterprise
│   └── publish_blog.sh
├── data/                      # 📊 Datos de ejecución
├── reports/                   # 📈 Informes generados
├── test_compliance.sh         # 🧪 Pipeline de prueba
├── deploy.sh                  # 🚀 Despliegue
├── CONTRIBUTING.md            # Normas de contribución
├── CHANGELOG.md               # Historial de versiones
├── LICENSE                    # MIT License
└── README.md                  # Este archivo
```

---

## Despliegue

Para producción en VPS:

```bash
./deploy.sh
```

O manualmente con systemd + nginx (ver [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) para instrucciones detalladas).

Servicios:
- **Dashboard**: `http://localhost:5000`
- **Payment**: `http://localhost:5002`
- **Continuous Audit**: `http://localhost:5003`

---

## Contribuir

Lee [CONTRIBUTING.md](CONTRIBUTING.md) para normas de código, pull requests y entorno de desarrollo.

---

## Licencia

MIT © 2026 CodeAudit Pro. Ver [LICENSE](LICENSE).

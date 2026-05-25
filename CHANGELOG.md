# Changelog

## v2.0.0 — 2026-05-25

### Versión Enterprise — Cumplimiento NIS2/DORA

#### 🚀 Nuevas funcionalidades
- **Escáneres reales**: Trivy (vulnerabilidades), Semgrep (SAST multi-lenguaje), Bandit (SAST Python), truffleHog (secretos).
- **Informe de cumplimiento normativo**: Mapeo automático de hallazgos a artículos NIS2 (Art. 21, 23) y DORA (Art. 5-30).
- **Certificación blockchain**: SHA-256, código QR de verificación, registro hash.
- **PDF descargable**: Informe compliance listo para auditor externo (weasyprint).

#### 🏢 Módulos Enterprise
- **Integración SIEM**: Envío de hallazgos críticos a Splunk HEC / Elasticsearch / webhook genérico.
- **Remediación automática**: PRs automáticos en GitHub para vulnerabilidades de dependencias; issues para secretos expuestos.
- **Portal white-label**: Personalización de colores, logo y subdominio por cliente.
- **Auditoría continua**: Webhooks GitHub (push/PR) + programación diaria/semanal con APScheduler.
- **Dashboard ejecutivo**: Panel "Cumplimiento Continuo" con evolución temporal, top vulnerabilidades por repo, MTTR, alertas WebSocket.

#### 💰 Planes de precio
- **Professional**: 9.900 €/año (hasta 10 repos, remediación básica).
- **Enterprise**: 29.900 €/año (hasta 50 repos, SIEM, white-label, soporte 24/7).
- **Custom**: Bajo demanda para >100 repos.

#### 🧹 Mejoras internas
- Refactor de `engine/run.sh` → `engine/run.py`.
- Snake_case en todos los archivos.
- `__init__.py` en todos los módulos Python.
- Documentación profesional: `README.md`, `CONTRIBUTING.md`, `enterprise_selling.md`, `docs/DEPLOYMENT.md`.

---

## v1.1.0 — 2026-05-20

- Integración Stripe para pagos.
- Dashboard Flask con login, tareas, leads.
- Landing page con formulario de contacto.
- Email automático al completar auditoría.

## v1.0.0 — 2026-05-10

- Auditoría básica con opencode CLI.
- Informe HTML ejecutivo.
- Despliegue con run-audit.sh.

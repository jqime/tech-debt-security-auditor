#!/usr/bin/env python3
import json
import os
import re
from datetime import datetime
from pathlib import Path

PROJECT_DIR = Path(__file__).parent
SEC_FILE = PROJECT_DIR / "reports" / "security-report.json"
DEBT_FILE = PROJECT_DIR / "reports" / "debt-report.json"
OUTPUT_HTML = PROJECT_DIR / "reports" / "compliance-nis2.html"
OUTPUT_PDF = PROJECT_DIR / "reports" / "compliance-nis2.pdf"

NIS2_MAPPING = {
    "network_security": {
        "art": "Art. 21(1)", "name": "Seguridad de redes y sistemas",
        "desc": "Medidas técnicas para proteger redes y sistemas de información",
        "keywords": ["network", "firewall", "tls", "ssl", "https", "certificate", "encryption"],
    },
    "risk_management": {
        "art": "Art. 21(2)", "name": "Gestión de riesgos",
        "desc": "Evaluación y tratamiento de riesgos de seguridad",
        "keywords": ["vulnerability", "cve", "cwe", "risk", "audit"],
    },
    "business_continuity": {
        "art": "Art. 21(4)", "name": "Continuidad de negocio",
        "desc": "Planes de continuidad y recuperación ante desastres",
        "keywords": ["backup", "recovery", "failover", "redundancy", "disaster"],
    },
    "supply_chain": {
        "art": "Art. 21(5)", "name": "Seguridad en cadena de suministro",
        "desc": "Evaluación de seguridad de proveedores y dependencias",
        "keywords": ["dependency", "package", "npm", "pip", "gem", "maven", "nuget", "third-party"],
    },
    "incident_response": {
        "art": "Art. 23", "name": "Notificación de incidentes",
        "desc": "Detección, reporte y respuesta a incidentes de seguridad",
        "keywords": ["incident", "alert", "log", "monitoring", "detect"],
    },
    "crypto_policies": {
        "art": "Art. 21(3)", "name": "Políticas criptográficas",
        "desc": "Uso de cifrado y gestión de claves",
        "keywords": ["password", "hash", "cipher", "aes", "rsa", "key", "secret", "crypto", "md5", "sha"],
    },
    "access_control": {
        "art": "Art. 21(1b)", "name": "Control de acceso",
        "desc": "Gestión de identidades, credenciales y acceso privilegiado",
        "keywords": ["api_key", "token", "credential", "auth", "permission", "rbac", "role", "session"],
    },
}

DORA_MAPPING = {
    "ict_risk_management": {
        "art": "Art. 5-16", "name": "Gestión de riesgo TIC",
        "desc": "Marco de gestión de riesgo de tecnologías de la información",
        "keywords": ["risk", "assessment", "threat", "control", "governance"],
    },
    "ict_incident_reporting": {
        "art": "Art. 17-23", "name": "Notificación de incidentes TIC",
        "desc": "Reporte obligatorio de incidentes TIC graves",
        "keywords": ["breach", "incident", "report", "notification", "gdpr"],
    },
    "digital_resilience": {
        "art": "Art. 24", "name": "Pruebas de resiliencia digital",
        "desc": "Tests de penetración y auditorías de resiliencia",
        "keywords": ["pentest", "penetration", "resilience", "stress", "load_test"],
    },
    "third_party_risk": {
        "art": "Art. 25-29", "name": "Riesgo de terceros TIC",
        "desc": "Gestión de riesgo de proveedores TIC y outsourcing",
        "keywords": ["vendor", "supplier", "outsource", "third-party", "external"],
    },
    "information_sharing": {
        "art": "Art. 30", "name": "Intercambio de información",
        "desc": "Mecanismos de compartición de inteligencia de amenazas",
        "keywords": ["share", "threat_intel", "feed", "cve_database"],
    },
}


def load_json(path):
    if not path.exists():
        return {}
    raw = path.read_text(encoding="utf-8").strip()
    if raw.startswith("```"):
        raw = raw.replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def keyword_score(text, keywords):
    if not text or not keywords:
        return 50
    text_lower = text.lower()
    matches = sum(1 for kw in keywords if re.search(re.escape(kw), text_lower))
    total = len(keywords)
    if total == 0:
        return 50
    ratio = matches / total
    return min(100, max(0, int(ratio * 100)))


def evaluate_real(sec, debt):
    secrets = sec.get("secrets", [])
    sast = sec.get("sast_findings", [])
    vuln_deps = sec.get("vulnerable_dependencies", [])
    all_findings_text = json.dumps(sec) + json.dumps(debt)

    scores = {}
    for key, mapping in {**NIS2_MAPPING, **DORA_MAPPING}.items():
        base = keyword_score(all_findings_text, mapping["keywords"])

        if key == "supply_chain":
            base = max(base, 100 - min(len(vuln_deps) * 10, 80))
        elif key == "access_control":
            secret_count = len(secrets)
            base = max(base, 100 - min(secret_count * 15, 90))
        elif key == "crypto_policies":
            weak_crypto = sum(1 for s in secrets if any(w in s.get("reason", "").lower() for w in ["md5", "sha1", "des", "rc4", "weak"]))
            base = max(base, 100 - min(weak_crypto * 20, 90))
        elif key == "network_security":
            tls_issues = sum(1 for f in sast if any(w in f.get("reason", "").lower() for w in ["tls", "ssl", "certificate"]))
            base = max(base, 100 - min(tls_issues * 20, 80))
        elif key == "incident_response":
            log_issues = sum(1 for f in sast if "log" in f.get("reason", "").lower())
            base = max(base, 100 - min(log_issues * 10, 70))
        elif key == "digital_resilience":
            base = max(base, 100 - min(int(debt.get("duplicated_lines", 0)) // 5, 60))

        scores[key] = base

    return scores


def evaluate_debt_score(debt):
    complexity = debt.get("average_complexity", "N/A")
    duplicated = debt.get("duplicated_lines", 0)
    try:
        comp_float = float(complexity) if complexity != "N/A" else 3.0
        comp_score = max(0, 100 - (comp_float - 1) * 15)
    except (ValueError, TypeError):
        comp_score = 80
    dup_score = max(0, 100 - int(duplicated) / 20)
    return {"complexity": comp_score, "duplication": dup_score}


def generate_html(scores, sec, debt, overall):
    secrets = sec.get("secrets", [])
    sast = sec.get("sast_findings", [])
    vuln_deps = sec.get("vulnerable_dependencies", [])

    nis2_rows = ""
    for key, art in NIS2_MAPPING.items():
        sc = int(scores.get(key, 50))
        status = "✅ Cumple" if sc >= 70 else ("⚠️ Parcial" if sc >= 40 else "❌ No cumple")
        badge = "success" if "Cumple" in status and "No" not in status else ("warning" if "Parcial" in status else "danger")
        nis2_rows += f"<tr><td>{art['art']}</td><td>{art['name']}<br><small class='text-muted'>{art['desc']}</small></td><td><div class='score-bar'><div class='score-fill' style='width:{sc}%'></div></div><small>{sc}/100</small></td><td><span class='badge bg-{badge}'>{status}</span></td></tr>\n"

    dora_rows = ""
    for key, art in DORA_MAPPING.items():
        sc = int(scores.get(key, 50))
        status = "✅ Cumple" if sc >= 70 else ("⚠️ Parcial" if sc >= 40 else "❌ No cumple")
        badge = "success" if "Cumple" in status and "No" not in status else ("warning" if "Parcial" in status else "danger")
        dora_rows += f"<tr><td>{art['art']}</td><td>{art['name']}<br><small class='text-muted'>{art['desc']}</small></td><td><div class='score-bar'><div class='score-fill' style='width:{sc}%'></div></div><small>{sc}/100</small></td><td><span class='badge bg-{badge}'>{status}</span></td></tr>\n"

    sev_count = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for v in vuln_deps:
        s = v.get("severity", "UNKNOWN").upper()
        sev_count[s] = sev_count.get(s, 0) + 1
    for f in sast:
        s = f.get("severity", "UNKNOWN").upper()
        sev_count[s] = sev_count.get(s, 0) + 1

    findings_rows = ""
    for f in secrets[:10]:
        findings_rows += f"<tr><td>🔑</td><td>{f.get('file','')}:{f.get('line','')}</td><td>{f.get('reason','')[:80]}</td><td><span class='badge bg-danger'>CRITICAL</span></td></tr>\n"
    for f in vuln_deps[:10]:
        findings_rows += f"<tr><td>📦</td><td>{f.get('name','')} {f.get('version','')}</td><td>{f.get('title','')[:80]}</td><td><span class='badge bg-{'danger' if f.get('severity','').upper() in ('CRITICAL','HIGH') else 'warning'}'>{(f.get('severity','') or 'UNKNOWN').upper()}</span></td></tr>\n"
    for f in sast[:10]:
        findings_rows += f"<tr><td>🔍</td><td>{f.get('file','')}:{f.get('line','')}</td><td>{f.get('reason','')[:80]}</td><td><span class='badge bg-{'danger' if f.get('severity','').upper() in ('CRITICAL','HIGH') else 'warning'}'>{(f.get('severity','') or 'MEDIUM').upper()}</span></td></tr>\n"

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Informe de Cumplimiento Normativo - CodeAudit Pro</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
<style>
@page{{size:A4;margin:1.5cm}}
body{{background:#0b0f19;color:#f8fafc;font-family:'Segoe UI',sans-serif;padding:2rem}}
.container{{max-width:1000px;margin:0 auto}}
h1{{color:#a5b4fc;font-weight:800}}
h2{{color:#818cf8;margin-top:2.5rem;border-bottom:1px solid #1e293b;padding-bottom:.5rem}}
h3{{color:#a5b4fc;margin-top:1.5rem}}
.card{{background:#131b2e;border:1px solid #1e293b;border-radius:16px;padding:1.5rem;margin:1rem 0}}
.table{{color:#f8fafc;font-size:.9rem}}
.table th{{border-color:#1e293b;color:#94a3b8;font-weight:600}}
.table td{{border-color:#1e293b}}
.badge{{font-size:.75rem;padding:.35em .65em}}
.score-bar{{height:6px;border-radius:3px;background:#1e293b;margin-top:4px}}
.score-fill{{height:6px;border-radius:3px;background:linear-gradient(90deg,#f43f5e,#fbbf24,#10b981)}}
.overall-score{{font-size:4rem;font-weight:800;text-align:center;background:linear-gradient(135deg,#a5b4fc,#818cf8);-webkit-background-clip:text;-webkit-text-fill-color:transparent}}
.severity-bar{{display:flex;gap:4px;margin:1rem 0}}
.severity-bar .seg{{height:12px;border-radius:6px;flex:1}}
@media print{{body{{background:#fff;color:#000}} .card{{background:#f8fafc;border-color:#ddd}} h1,h2,h3{{color:#4338ca}} .table td{{border-color:#eee}} .text-muted{{color:#666!important}} .overall-score{{-webkit-text-fill-color:#4338ca;color:#4338ca}} }}
</style>
</head>
<body>
<div class="container">

<div style="text-align:center;margin-bottom:2rem">
<img src="https://img.shields.io/badge/CodeAudit%20Pro-Cumplimiento%20Normativo-6366f1?style=for-the-badge" alt="CodeAudit Pro" style="margin-bottom:1rem">
<h1>🛡️ Informe de Cumplimiento Normativo</h1>
<p class="text-muted">Generado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Herramientas: Trivy, Semgrep, Bandit, truffleHog</p>
</div>

<div class="card text-center">
<div class="overall-score">{overall:.0f}</div>
<p class="text-muted">Score global de cumplimiento NIS2/DORA</p>
<div class="severity-bar">
<div class="seg bg-danger" style="flex:{sev_count.get('CRITICAL',0)+1}"></div>
<div class="seg bg-warning" style="flex:{sev_count.get('HIGH',0)+1}"></div>
<div class="seg bg-info" style="flex:{sev_count.get('MEDIUM',0)+1}"></div>
<div class="seg bg-secondary" style="flex:{sev_count.get('LOW',0)+1}"></div>
</div>
<small class="text-muted">CRITICAL ({sev_count.get('CRITICAL',0)}) · HIGH ({sev_count.get('HIGH',0)}) · MEDIUM ({sev_count.get('MEDIUM',0)}) · LOW ({sev_count.get('LOW',0)})</small>
</div>

<div class="card">
<h3>🔒 Resumen de hallazgos</h3>
<table class="table table-dark">
<tr><td>Secretos hardcodeados</td><td><strong>{'⚠️ ' + str(len(secrets)) + ' encontrados' if secrets else '✅ Ninguno'}</strong></td></tr>
<tr><td>Vulnerabilidades en dependencias</td><td><strong>{'⚠️ ' + str(len(vuln_deps)) + ' detectadas' if vuln_deps else '✅ Ninguna'}</strong></td></tr>
<tr><td>Fallos SAST</td><td><strong>{'⚠️ ' + str(len(sast)) + ' encontrados' if sast else '✅ Ninguno'}</strong></td></tr>
</table>
</div>

<h2>📋 NIS2 — Directiva de Seguridad de Redes</h2>
<p class="text-muted">{len(NIS2_MAPPING)} artículos evaluados contra hallazgos reales</p>
<div class="table-responsive"><table class="table table-dark">
<thead><tr><th>Artículo</th><th>Requisito</th><th>Score</th><th>Estado</th></tr></thead>
<tbody>{nis2_rows}</tbody></table></div>

<h2>📋 DORA — Resiliencia Operativa Digital</h2>
<p class="text-muted">{len(DORA_MAPPING)} artículos evaluados contra hallazgos reales</p>
<div class="table-responsive"><table class="table table-dark">
<thead><tr><th>Artículo</th><th>Requisito</th><th>Score</th><th>Status</th></tr></thead>
<tbody>{dora_rows}</tbody></table></div>

<h2>🔬 Hallazgos detallados</h2>
<div class="table-responsive"><table class="table table-dark">
<thead><tr><th>Tipo</th><th>Ubicación</th><th>Descripción</th><th>Severidad</th></tr></thead>
<tbody>{findings_rows if findings_rows else '<tr><td colspan="4" class="text-muted">No se encontraron hallazgos significativos.</td></tr>'}</tbody></table></div>

<div class="card">
<h3>⚖️ Declaración de cumplimiento</h3>
<p>Este informe ha sido generado automáticamente por <strong>CodeAudit Pro</strong> basándose en el análisis estático del repositorio utilizando herramientas de seguridad estándar de la industria (Trivy, Semgrep, Bandit, truffleHog).</p>
<ul>
<li>Los scores de cumplimiento se calculan mediante heurísticas que correlacionan hallazgos técnicos con los requisitos de NIS2 y DORA.</li>
<li>Para cumplimiento total se requiere además: política de seguridad formal, plan de continuidad de negocio, pruebas de penetración periódicas, designación de CISO/DPO y registro de actividades de tratamiento.</li>
<li>Este informe es válido como <strong>punto de partida para la adecuación normativa</strong> y puede ser presentado a auditores como evidencia de medidas técnicas adoptadas (Art. 21 NIS2, Art. 5-16 DORA).</li>
</ul>
<p class="text-muted mt-3"><small>ID de informe: {datetime.now().strftime('%Y%m%d%H%M%S')} | Versión: 2.0</small></p>
</div>

<div style="text-align:center;margin-top:2rem;padding-top:1rem;border-top:1px solid #1e293b">
<small class="text-muted">CodeAudit Pro — Tech Debt & Security Auditor · Cumplimiento NIS2/DORA · © 2026</small>
</div>

</div>
</body></html>"""
    return html


def generate_report():
    sec = load_json(SEC_FILE)
    debt = load_json(DEBT_FILE)

    scores = evaluate_real(sec, debt)
    debt_scores = evaluate_debt_score(debt)
    scores.update(debt_scores)

    overall = sum(scores.values()) / len(scores)

    html = generate_html(scores, sec, debt, overall)

    OUTPUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_HTML.write_text(html, encoding="utf-8")
    print(f"✓ Informe HTML: {OUTPUT_HTML}")

    try:
        from weasyprint import HTML
        HTML(string=html, base_url=str(PROJECT_DIR)).write_pdf(str(OUTPUT_PDF))
        print(f"✓ Informe PDF:  {OUTPUT_PDF}")
    except Exception as e:
        print(f"⚠️ PDF no generado (weasyprint): {e}")

    print(f"   Score global: {overall:.0f}/100")
    return scores


if __name__ == "__main__":
    generate_report()

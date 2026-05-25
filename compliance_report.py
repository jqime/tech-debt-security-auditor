#!/usr/bin/env python3
import json
import os
from datetime import datetime
from pathlib import Path

PROJECT_DIR = Path(__file__).parent

SEC_FILE = PROJECT_DIR / "reports" / "security-report.json"
DEBT_FILE = PROJECT_DIR / "reports" / "debt-report.json"
OUTPUT_FILE = PROJECT_DIR / "reports" / "compliance-nis2.html"

NIS2_ARTICLES = {
    "network_security": {"art": "Art. 21(1)", "name": "Seguridad de redes y sistemas", "desc": "Medidas técnicas para proteger redes y sistemas de información"},
    "risk_management": {"art": "Art. 21(2)", "name": "Gestión de riesgos", "desc": "Evaluación y tratamiento de riesgos de seguridad"},
    "business_continuity": {"art": "Art. 21(4)", "name": "Continuidad de negocio", "desc": "Planes de continuidad y recuperación ante desastres"},
    "supply_chain": {"art": "Art. 21(5)", "name": "Seguridad en cadena de suministro", "desc": "Evaluación de seguridad de proveedores y dependencias"},
    "incident_response": {"art": "Art. 23", "name": "Notificación de incidentes", "desc": "Detección, reporte y respuesta a incidentes de seguridad"},
    "crypto_policies": {"art": "Art. 21(3)", "name": "Políticas criptográficas", "desc": "Uso de cifrado y gestión de claves"},
    "access_control": {"art": "Art. 21(1b)", "name": "Control de acceso", "desc": "Gestión de identidades, credenciales y acceso privilegiado"},
}

DORA_ARTICLES = {
    "ict_risk_management": {"art": "Art. 5-16", "name": "Gestión de riesgo TIC", "desc": "Marco de gestión de riesgo de tecnologías de la información"},
    "ict_incident_reporting": {"art": "Art. 17-23", "name": "Notificación de incidentes TIC", "desc": "Reporte obligatorio de incidentes TIC graves"},
    "digital_resilience": {"art": "Art. 24", "name": "Pruebas de resiliencia digital", "desc": "Tests de penetración y auditorías de resiliencia"},
    "third_party_risk": {"art": "Art. 25-29", "name": "Riesgo de terceros TIC", "desc": "Gestión de riesgo de proveedores TIC y outsourcing"},
    "information_sharing": {"art": "Art. 30", "name": "Intercambio de información", "desc": "Mecanismos de compartición de inteligencia de amenazas"},
}


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    raw = path.read_text(encoding="utf-8").strip()
    if raw.startswith("```"):
        raw = raw.replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def evaluate_security(sec: dict) -> dict:
    secrets = sec.get("secrets", [])
    deps = sec.get("vulnerable_dependencies", [])
    result = {}

    secrets_ok = len(secrets) == 0
    deps_critical = sum(1 for d in deps if d.get("severity", "").upper() in ("CRITICAL", "HIGH"))
    deps_ok = deps_critical == 0

    result["network_security"] = 60 if secrets_ok else 20
    result["risk_management"] = 80 if secrets_ok and deps_ok else 30
    result["business_continuity"] = 70 if deps_ok else 40
    result["supply_chain"] = 75 if deps_ok else 25
    result["incident_response"] = 65 if secrets_ok else 35
    result["crypto_policies"] = 85 if secrets_ok else 50
    result["access_control"] = 90 if secrets_ok else 30

    result["ict_risk_management"] = 70 if secrets_ok and deps_ok else 30
    result["ict_incident_reporting"] = 60 if secrets_ok else 25
    result["digital_resilience"] = 55 if deps_ok else 20
    result["third_party_risk"] = 75 if deps_ok else 30
    result["information_sharing"] = 50

    return result


def evaluate_debt(debt: dict) -> dict:
    complexity = debt.get("average_complexity", "N/A")
    duplicated = debt.get("duplicated_lines", 0)

    try:
        comp_float = float(complexity)
        comp_score = max(0, 100 - (comp_float - 1) * 20)
    except (ValueError, TypeError):
        comp_score = 80

    dup_score = max(0, 100 - (int(duplicated) / 20))

    return {
        "complexity": comp_score,
        "duplication": dup_score,
    }


def generate_report():
    sec = load_json(SEC_FILE)
    debt = load_json(DEBT_FILE)
    scores = evaluate_security(sec)
    debt_scores = evaluate_debt(debt)
    scores.update(debt_scores)

    secrets_count = len(sec.get("secrets", []))
    vuln_count = len(sec.get("vulnerable_dependencies", []))
    overall = sum(scores.values()) / len(scores)

    nis2_status = []
    for key, art in NIS2_ARTICLES.items():
        score = scores.get(key, 50)
        if score >= 70:
            status = "✅ Cumple"
        elif score >= 40:
            status = "⚠️ Parcial"
        else:
            status = "❌ No cumple"
        nis2_status.append((art["art"], art["name"], score, status))

    dora_status = []
    for key, art in DORA_ARTICLES.items():
        score = scores.get(key, 50)
        if score >= 70:
            status = "✅ Cumple"
        elif score >= 40:
            status = "⚠️ Parcial"
        else:
            status = "❌ No cumple"
        dora_status.append((art["art"], art["name"], score, status))

    html = f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Informe de Cumplimiento Normativo - CodeAudit Pro</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
<style>
body{{background:#0b0f19;color:#f8fafc;font-family:'Segoe UI',sans-serif;padding:2rem}}
.container{{max-width:1000px;margin:0 auto}}
h1{{color:#a5b4fc;font-weight:800}}
h2{{color:#818cf8;margin-top:2.5rem;border-bottom:1px solid #1e293b;padding-bottom:.5rem}}
.card{{background:#131b2e;border:1px solid #1e293b;border-radius:16px;padding:1.5rem;margin:1rem 0}}
.table{{color:#f8fafc}}.table th{{border-color:#1e293b;color:#94a3b8;font-weight:600}}
.table td{{border-color:#1e293b}}
.badge{{font-size:.8rem;padding:.35em .65em}}
.score-bar{{height:8px;border-radius:4px;background:#1e293b;margin-top:4px}}
.score-fill{{height:8px;border-radius:4px;background:linear-gradient(90deg,#f43f5e,#fbbf24,#10b981)}}
.overall-score{{font-size:4rem;font-weight:800;text-align:center;background:linear-gradient(135deg,#a5b4fc,#818cf8);-webkit-background-clip:text;-webkit-text-fill-color:transparent}}
</style></head>
<body>
<div class="container">
<h1>🛡️ Informe de Cumplimiento Normativo</h1>
<p class="text-muted">Generado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>

<div class="card text-center">
<div class="overall-score">{overall:.0f}</div>
<p class="text-muted">Score global de cumplimiento</p>
</div>

<div class="card">
<h3>🔒 Hallazgos de seguridad</h3>
<p>Secretos hardcodeados: <strong>{'⚠️ ' + str(secrets_count) + ' encontrados' if secrets_count else '✅ Ninguno'}</strong></p>
<p>Vulnerabilidades: <strong>{'⚠️ ' + str(vuln_count) + ' detectadas' if vuln_count else '✅ Ninguna'}</strong></p>
</div>

<h2>📋 NIS2 — Directiva de Seguridad de Redes</h2>
<p class="text-muted">{len(nis2_status)} artículos evaluados</p>
<div class="table-responsive"><table class="table table-dark">
<thead><tr><th>Artículo</th><th>Requisito</th><th>Score</th><th>Estado</th></tr></thead>
<tbody>
"""
    for art_id, name, score, status in nis2_status:
        bar_style = f"width:{score}%"
        html += f"<tr><td>{art_id}</td><td>{name}</td><td><div class='score-bar'><div class='score-fill' style='{bar_style}'></div></div><small class='text-muted'>{score:.0f}/100</small></td><td><span class='badge bg-{'success' if 'Cumple' in status and 'No' not in status else 'warning' if 'Parcial' in status else 'danger'}'>{status}</span></td></tr>\n"

    html += """</tbody></table></div>

<h2>📋 DORA — Resiliencia Operativa Digital</h2>
<p class="text-muted">""" + str(len(dora_status)) + """ artículos evaluados</p>
<div class="table-responsive"><table class="table table-dark">
<thead><tr><th>Artículo</th><th>Requisito</th><th>Score</th><th>Estado</th></tr></thead>
<tbody>
"""
    for art_id, name, score, status in dora_status:
        bar_style = f"width:{score}%"
        html += f"<tr><td>{art_id}</td><td>{name}</td><td><div class='score-bar'><div class='score-fill' style='{bar_style}'></div></div><small class='text-muted'>{score:.0f}/100</small></td><td><span class='badge bg-{'success' if 'Cumple' in status and 'No' not in status else 'warning' if 'Parcial' in status else 'danger'}'>{status}</span></td></tr>\n"

    html += """</tbody></table></div>

<div class="card">
<h3>⚖️ Declaración de cumplimiento</h3>
<p>Este informe ha sido generado automáticamente por CodeAudit Pro basándose en el análisis estático del repositorio.</p>
<ul>
<li>El score de cumplimiento es una estimación basada en hallazgos técnicos y no constituye una certificación oficial.</li>
<li>Para cumplimiento total con NIS2/DORA se requiere además: política de seguridad formal, plan de continuidad de negocio, pruebas de penetración periódicas y designación de CISO.</li>
<li>Este informe es válido como punto de partida para la adecuación normativa y puede ser presentado a auditores como evidencia de medidas técnicas adoptadas.</li>
</ul>
</div>

<div class="card">
<h3>📎 Auditorías asociadas</h3>
<p>Security: <code>reports/security-report.json</code></p>
<p>Deuda técnica: <code>reports/debt-report.json</code></p>
</div>

</div>
</body></html>"""

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(html, encoding="utf-8")
    print(f"✓ Informe de cumplimiento NIS2/DORA generado: {OUTPUT_FILE}")
    return scores


if __name__ == "__main__":
    generate_report()

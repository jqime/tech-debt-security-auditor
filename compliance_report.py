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


def _calculate_fine(scores, sec, debt):
    secrets = sec.get("secrets", [])
    sast = sec.get("sast_findings", [])
    vuln_deps = sec.get("vulnerable_dependencies", [])

    n_criticos = sum(1 for f in sast if f.get("severity", "").upper() in ("CRITICAL", "HIGH"))
    n_criticos += sum(1 for s in secrets if s.get("severity", "").upper() in ("CRITICAL", "HIGH"))
    n_medios = sum(1 for f in sast if f.get("severity", "").upper() == "MEDIUM")
    n_medios += sum(1 for s in secrets if s.get("severity", "").upper() == "MEDIUM")
    n_vuln_deps = len(vuln_deps)
    n_secrets = len(secrets)
    n_sast = len(sast)

    # Base calculation: each critical finding adds risk
    base_risk = 0
    base_risk += n_criticos * 1_500_000    # up to 1.5M per critical
    base_risk += n_medios * 300_000         # up to 300k per medium
    base_risk += n_vuln_deps * 100_000      # 100k per vulnerable dependency
    base_risk += n_secrets * 250_000        # 250k per exposed secret
    base_risk += n_sast * 50_000            # 50k per SAST finding

    # Cap at realistic NIS2 maximum
    max_fine = 10_000_000
    fine_amount = min(base_risk, max_fine)

    # Determine violated articles
    violated_articles = []
    for key, mapping in NIS2_MAPPING.items():
        if scores.get(key, 50) < 40:
            violated_articles.append(f"{mapping['art']} — {mapping['name']}")
    for key, mapping in DORA_MAPPING.items():
        if scores.get(key, 50) < 40:
            violated_articles.append(f"{mapping['art']} — {mapping['name']}")

    dora_fine = fine_amount // 2  # DORA: typically lower than NIS2

    if fine_amount >= 7_000_000:
        text = f"HASTA {fine_amount:,} €".replace(",", ".")
        color = "#f43f5e"
    elif fine_amount >= 2_000_000:
        text = f"HASTA {fine_amount:,} €".replace(",", ".")
        color = "#fbbf24"
    elif fine_amount >= 500_000:
        text = f"~{fine_amount:,} €".replace(",", ".")
        color = "#fbbf24"
    else:
        text = f"BAJO — ~{fine_amount:,} €".replace(",", ".")
        color = "#10b981"

    articles_html = "<br>".join(
        f"<span style='color:#f43f5e;font-size:0.78rem;'>• {a}</span>"
        for a in violated_articles[:5]
    )
    if len(violated_articles) > 5:
        articles_html += f"<br><span style='color:#64748b;font-size:0.72rem;'>+{len(violated_articles)-5} artículos más</span>"

    return {
        "text": text,
        "color": color,
        "amount": fine_amount,
        "articles": articles_html,
        "dora_fine": dora_fine,
        "n_criticos": n_criticos,
        "n_medios": n_medios,
        "n_secrets": n_secrets,
        "n_vuln_deps": n_vuln_deps,
    }


def generate_html(scores, sec, debt, overall):
    import hashlib
    secrets = sec.get("secrets", [])
    sast = sec.get("sast_findings", [])
    vuln_deps = sec.get("vulnerable_dependencies", [])

    nis2_rows = ""
    for key, art in NIS2_MAPPING.items():
        sc = int(scores.get(key, 50))
        icon = "✅" if sc >= 70 else ("⚠️" if sc >= 40 else "❌")
        txt = "Cumple" if sc >= 70 else ("Parcial" if sc >= 40 else "No cumple")
        c = "#10b981" if sc >= 70 else ("#fbbf24" if sc >= 40 else "#f43f5e")
        nis2_rows += f"""<tr>
<td style="padding:12px 16px;border-bottom:1px solid #1e293b;font-weight:600;color:#e2e8f0">{art['art']}</td>
<td style="padding:12px 16px;border-bottom:1px solid #1e293b;color:#cbd5e1">{art['name']}<br><span style="font-size:0.8rem;color:#64748b">{art['desc']}</span></td>
<td style="padding:12px 16px;border-bottom:1px solid #1e293b">
<div style="height:6px;border-radius:3px;background:#1e293b;margin-bottom:4px;overflow:hidden"><div style="height:6px;border-radius:3px;width:{sc}%;background:linear-gradient(90deg,#6366f1,#a5b4fc)"></div></div>
<span style="font-size:0.75rem;color:#64748b">{sc}/100</span></td>
<td style="padding:12px 16px;border-bottom:1px solid #1e293b">
<span style="display:inline-flex;align-items:center;gap:4px;padding:4px 12px;border-radius:999px;font-size:0.75rem;font-weight:600;background:{c}20;color:{c}">{icon} {txt}</span></td>
</tr>\n"""

    dora_rows = ""
    for key, art in DORA_MAPPING.items():
        sc = int(scores.get(key, 50))
        icon = "✅" if sc >= 70 else ("⚠️" if sc >= 40 else "❌")
        txt = "Cumple" if sc >= 70 else ("Parcial" if sc >= 40 else "No cumple")
        c = "#10b981" if sc >= 70 else ("#fbbf24" if sc >= 40 else "#f43f5e")
        dora_rows += f"""<tr>
<td style="padding:12px 16px;border-bottom:1px solid #1e293b;font-weight:600;color:#e2e8f0">{art['art']}</td>
<td style="padding:12px 16px;border-bottom:1px solid #1e293b;color:#cbd5e1">{art['name']}<br><span style="font-size:0.8rem;color:#64748b">{art['desc']}</span></td>
<td style="padding:12px 16px;border-bottom:1px solid #1e293b">
<div style="height:6px;border-radius:3px;background:#1e293b;margin-bottom:4px;overflow:hidden"><div style="height:6px;border-radius:3px;width:{sc}%;background:linear-gradient(90deg,#6366f1,#a5b4fc)"></div></div>
<span style="font-size:0.75rem;color:#64748b">{sc}/100</span></td>
<td style="padding:12px 16px;border-bottom:1px solid #1e293b">
<span style="display:inline-flex;align-items:center;gap:4px;padding:4px 12px;border-radius:999px;font-size:0.75rem;font-weight:600;background:{c}20;color:{c}">{icon} {txt}</span></td>
</tr>\n"""

    sev_count = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for v in vuln_deps:
        s = v.get("severity", "UNKNOWN").upper()
        sev_count[s] = sev_count.get(s, 0) + 1
    for f in sast:
        s = f.get("severity", "UNKNOWN").upper()
        sev_count[s] = sev_count.get(s, 0) + 1

    fine = _calculate_fine(scores, sec, debt)
    fine_text = fine["text"]
    fine_color = fine["color"]
    fine_articles = fine["articles"]
    fine_refs = " · ".join(filter(None, [
        f"<span style='color:{fine_color};font-weight:700;'>{fine['n_criticos']} críticos</span>" if fine['n_criticos'] else "",
        f"<span style='color:{fine_color};'>{fine['n_medios']} medios</span>" if fine['n_medios'] else "",
        f"<span style='color:{fine_color};'>{fine['n_secrets']} secretos</span>" if fine['n_secrets'] else "",
        f"<span style='color:{fine_color};'>{fine['n_vuln_deps']} dependencias vulnerables</span>" if fine['n_vuln_deps'] else "",
        "sin hallazgos" if not any([fine['n_criticos'], fine['n_medios'], fine['n_secrets'], fine['n_vuln_deps']]) else "",
    ]))

    score_color = "#f43f5e" if overall < 40 else ("#fbbf24" if overall < 70 else "#10b981")

    cert_data = json.dumps({k: scores.get(k) for k in {**NIS2_MAPPING, **DORA_MAPPING}}, sort_keys=True)
    cert_hash = hashlib.sha256(cert_data.encode()).hexdigest()

    actions = []
    if secrets:
        actions.append(("🔴 CRÍTICA", "Eliminar secretos hardcodeados", f"Se detectaron {len(secrets)} secretos en el código. Rotar credenciales inmediatamente y configurar pre-commit hooks.", "#f43f5e"))
    if vuln_deps:
        actions.append(("🔴 CRÍTICA", "Actualizar dependencias vulnerables", f"Se encontraron {len(vuln_deps)} dependencias con CVEs conocidos. Actualizar a versiones parcheadas.", "#f43f5e"))
    if sast:
        actions.append(("🟡 IMPORTANTE", "Corregir fallos SAST", f"{len(sast)} hallazgos de análisis estático requieren revisión.", "#fbbf24"))
    if debt.get("duplicated_lines", 0) > 0:
        actions.append(("🟡 IMPORTANTE", "Reducir código duplicado", f"{debt.get('duplicated_lines', 0)} líneas duplicadas incrementan el riesgo de mantenimiento.", "#fbbf24"))
    actions.append(("🟢 RECOMENDADO", "Implementar pruebas de penetración", "Pruebas de resiliencia digital requeridas por DORA Art. 24.", "#6366f1"))

    actions_html = ""
    for i, (priority, title, desc, color) in enumerate(actions, 1):
        actions_html += f"""<div style="display:flex;gap:16px;padding:16px;background:rgba(30,41,59,0.5);border-radius:12px;border-left:4px solid {color};margin-bottom:12px">
<div style="min-width:32px;height:32px;border-radius:50%;background:{color}20;display:flex;align-items:center;justify-content:center;color:{color};font-size:0.8rem;font-weight:700">{i}</div>
<div>
<div style="font-size:0.75rem;font-weight:700;color:{color};text-transform:uppercase;letter-spacing:0.05em;margin-bottom:2px">{priority}</div>
<div style="font-weight:600;color:#e2e8f0;margin-bottom:4px">{title}</div>
<div style="font-size:0.85rem;color:#94a3b8">{desc}</div>
</div>
</div>\n"""

    findings_rows = ""
    for f in secrets[:10]:
        findings_rows += f"""<tr>
<td style="padding:10px 12px;border-bottom:1px solid #1e293b;text-align:center">🔑</td>
<td style="padding:10px 12px;border-bottom:1px solid #1e293b;font-family:monospace;font-size:0.8rem;color:#38bdf8">{f.get('file','')}:{f.get('line','')}</td>
<td style="padding:10px 12px;border-bottom:1px solid #1e293b;color:#94a3b8">{f.get('reason','')[:80]}</td>
<td style="padding:10px 12px;border-bottom:1px solid #1e293b;text-align:center"><span style="display:inline-block;padding:2px 10px;border-radius:999px;font-size:0.7rem;font-weight:700;background:#f43f5e20;color:#f43f5e">CRITICAL</span></td>
</tr>\n"""
    for f in vuln_deps[:10]:
        sev = (f.get('severity', '') or 'UNKNOWN').upper()
        sc = "#f43f5e" if sev in ("CRITICAL", "HIGH") else "#fbbf24"
        findings_rows += f"""<tr>
<td style="padding:10px 12px;border-bottom:1px solid #1e293b;text-align:center">📦</td>
<td style="padding:10px 12px;border-bottom:1px solid #1e293b;font-family:monospace;font-size:0.8rem;color:#38bdf8">{f.get('name','')} {f.get('version','')}</td>
<td style="padding:10px 12px;border-bottom:1px solid #1e293b;color:#94a3b8">{f.get('title','')[:80]}</td>
<td style="padding:10px 12px;border-bottom:1px solid #1e293b;text-align:center"><span style="display:inline-block;padding:2px 10px;border-radius:999px;font-size:0.7rem;font-weight:700;background:{sc}20;color:{sc}">{sev}</span></td>
</tr>\n"""
    for f in sast[:10]:
        sev = (f.get('severity', '') or 'MEDIUM').upper()
        sc = "#f43f5e" if sev in ("CRITICAL", "HIGH") else ("#fbbf24" if sev == "MEDIUM" else "#94a3b8")
        findings_rows += f"""<tr>
<td style="padding:10px 12px;border-bottom:1px solid #1e293b;text-align:center">🔍</td>
<td style="padding:10px 12px;border-bottom:1px solid #1e293b;font-family:monospace;font-size:0.8rem;color:#38bdf8">{f.get('file','')}:{f.get('line','')}</td>
<td style="padding:10px 12px;border-bottom:1px solid #1e293b;color:#94a3b8">{f.get('reason','')[:80]}</td>
<td style="padding:10px 12px;border-bottom:1px solid #1e293b;text-align:center"><span style="display:inline-block;padding:2px 10px;border-radius:999px;font-size:0.7rem;font-weight:700;background:{sc}20;color:{sc}">{sev}</span></td>
</tr>\n"""

    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    report_id = datetime.now().strftime('%Y%m%d%H%M%S')

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Cumplimiento NIS2/DORA - Informe de Auditoría | CodeAudit Pro</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:#0b0f19;color:#f8fafc;font-family:'Segoe UI','Inter',system-ui,sans-serif;line-height:1.6}}
.container{{max-width:1000px;margin:0 auto;padding:2rem 1.5rem}}
.hero{{background:linear-gradient(135deg,#0f1529,#1a1f3a);border:1px solid #1e293b;border-radius:20px;padding:3rem 2rem;text-align:center;position:relative;overflow:hidden;margin-bottom:2rem}}
.hero::before{{content:'';position:absolute;top:-60%;right:-10%;width:400px;height:400px;background:radial-gradient(circle,rgba(99,102,241,0.15),transparent 70%);pointer-events:none}}
.hero::after{{content:'';position:absolute;bottom:-30%;left:-10%;width:300px;height:300px;background:radial-gradient(circle,rgba(234,179,8,0.08),transparent 70%);pointer-events:none}}
.hero h1{{font-size:2rem;font-weight:800;background:linear-gradient(135deg,#fbbf24,#f59e0b,#6366f1);-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:0.5rem;position:relative;z-index:1}}
.hero .subtitle{{color:#94a3b8;font-size:0.9rem;position:relative;z-index:1}}
.hero .report-id{{color:#475569;font-size:0.75rem;margin-top:0.5rem;position:relative;z-index:1}}
.score-card{{background:linear-gradient(135deg,#131b2e,#1a2340);border:1px solid #1e293b;border-radius:20px;padding:2.5rem 2rem;text-align:center;margin-bottom:2rem}}
.score-ring{{width:140px;height:140px;border-radius:50%;background:conic-gradient({score_color} {overall:.0f}%,#1e293b 0%);display:flex;align-items:center;justify-content:center;margin:0 auto 1.5rem;position:relative}}
.score-ring::before{{content:'';position:absolute;width:110px;height:110px;border-radius:50%;background:#131b2e}}
.score-value{{font-size:3rem;font-weight:800;color:{score_color};position:relative;z-index:1}}
.score-label{{color:#94a3b8;font-size:0.85rem;margin-bottom:1.5rem}}
.fine-estimate{{background:rgba(30,41,59,0.5);border-radius:16px;padding:1.5rem 2rem;margin-bottom:1.5rem;border:1px solid rgba(30,41,59,0.8)}}
.fine-estimate .label{{color:#94a3b8;font-size:0.75rem;text-transform:uppercase;letter-spacing:0.05em;font-weight:600;margin-bottom:0.25rem}}
.fine-estimate .amount{{font-size:2rem;font-weight:800;color:{fine_color}}}
.fine-estimate .ref{{color:#475569;font-size:0.75rem;margin-top:0.25rem}}
.summary-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:1rem;margin-bottom:2rem}}
.summary-card{{background:#131b2e;border:1px solid #1e293b;border-radius:16px;padding:1.5rem;text-align:center;transition:all 0.3s ease}}
.summary-card:hover{{border-color:#6366f1;transform:translateY(-2px);box-shadow:0 8px 24px rgba(99,102,241,0.1)}}
.summary-card .num{{font-size:2.5rem;font-weight:800;background:linear-gradient(135deg,#a5b4fc,#818cf8);-webkit-background-clip:text;-webkit-text-fill-color:transparent;line-height:1}}
.summary-card .num.red{{background:linear-gradient(135deg,#f43f5e,#fb7185);-webkit-background-clip:text;-webkit-text-fill-color:transparent}}
.summary-card .num.amber{{background:linear-gradient(135deg,#fbbf24,#f59e0b);-webkit-background-clip:text;-webkit-text-fill-color:transparent}}
.summary-card .num.green{{background:linear-gradient(135deg,#10b981,#34d399);-webkit-background-clip:text;-webkit-text-fill-color:transparent}}
.summary-card .label{{color:#94a3b8;font-size:0.8rem;margin-top:0.5rem;font-weight:500}}
.section-title{{font-size:1.25rem;font-weight:700;color:#e2e8f0;margin:2rem 0 1rem;display:flex;align-items:center;gap:8px}}
.section-title .line{{flex:1;height:1px;background:linear-gradient(90deg,#1e293b,transparent)}}
.table-wrap{{background:#131b2e;border:1px solid #1e293b;border-radius:16px;overflow:hidden;margin-bottom:2rem}}
.table-wrap table{{width:100%;border-collapse:collapse;font-size:0.85rem}}
.table-wrap th{{padding:12px 16px;text-align:left;font-weight:600;color:#94a3b8;font-size:0.75rem;text-transform:uppercase;letter-spacing:0.05em;background:rgba(30,41,59,0.3);border-bottom:1px solid #1e293b}}
.cert-block{{background:linear-gradient(135deg,#0f1529,#131b2e);border:1px solid #1e293b;border-radius:16px;padding:2rem;margin:2rem 0;display:flex;flex-wrap:wrap;gap:2rem;align-items:center;justify-content:center}}
.cert-block .hash{{font-family:monospace;font-size:0.7rem;color:#64748b;word-break:break-all;max-width:300px}}
.cert-block .qr img{{border-radius:12px}}
.cert-block .cert-text{{text-align:center}}
.cert-block .cert-text .title{{color:#a5b4fc;font-weight:700;font-size:0.9rem}}
.cert-block .cert-text .sub{{color:#475569;font-size:0.75rem}}
.footer{{text-align:center;padding:1.5rem 0;border-top:1px solid #1e293b;margin-top:2rem}}
.footer .company{{color:#6366f1;font-weight:700}}
.footer .verify{{color:#475569;font-size:0.8rem;margin-top:4px}}
@page{{size:A4;margin:2cm;orphans:3;widows:3}} @page:first{{margin-top:3cm}} .table-wrap{{page-break-inside:auto}} .table-wrap table{{page-break-inside:auto}} .table-wrap tr{{page-break-inside:avoid;page-break-after:auto}} .table-wrap thead{{display:table-header-group}} .table-wrap tfoot{{display:table-footer-group}} .summary-card,.cert-block,.fine-estimate{{page-break-inside:avoid}} @media print{{body{{background:#fff!important;color:#000!important}} .hero,.score-card,.summary-card,.table-wrap,.cert-block{{background:#f8fafc!important;border-color:#ddd!important}} .hero h1,.summary-card .num,.summary-card .num.red,.summary-card .num.amber,.summary-card .num.green{{-webkit-text-fill-color:#4338ca!important;color:#4338ca!important}} .section-title,.cert-block .cert-text .title{{color:#4338ca!important}} .fine-estimate .amount,.score-value{{color:#4338ca!important}} .footer .company{{color:#4338ca!important}} .table-wrap th{{color:#666!important}} .score-ring{{background:conic-gradient(#4338ca {overall:.0f}%,#eee 0%)!important}}}}
</style>
</head>
<body>
<div class="container">

<div class="hero">
<h1>Cumplimiento NIS2/DORA — Informe de Auditoría</h1>
<p class="subtitle">Generado: {ts} · Herramientas: Trivy, Semgrep, Bandit, truffleHog</p>
<p class="report-id">ID: {report_id} · Versión 2.0</p>
</div>

<div class="score-card">
<div class="score-ring"><div class="score-value">{overall:.0f}</div></div>
<p class="score-label">Score global de cumplimiento normativo NIS2/DORA</p>
    <div class="fine-estimate">
<p class="label">Riesgo de multa potencial</p>
<p class="amount">{fine_text}</p>
<p class="ref" style="margin-bottom:0.5rem;">Según Art. 31 NIS2 (hasta 10M€ o 2% facturación) y Art. 50 DORA (hasta 1% volumen diario)</p>
<div style="font-size:0.72rem;color:#64748b;text-align:left;max-width:500px;margin:0 auto;padding-top:0.5rem;border-top:1px solid rgba(71,85,105,0.3);">
{fine_refs}
</div>
{fine.get('articles', '')}
</div>
</div>

<div class="summary-grid">
<div class="summary-card"><div class="num {'red' if secrets else 'green'}">{len(secrets)}</div><div class="label">Secretos Detectados</div></div>
<div class="summary-card"><div class="num {'red' if vuln_deps else 'green'}">{len(vuln_deps)}</div><div class="label">Vulnerabilidades</div></div>
<div class="summary-card"><div class="num {'red' if sast else 'green'}">{len(sast)}</div><div class="label">Fallos SAST</div></div>
<div class="summary-card"><div class="num red">{sev_count.get('CRITICAL',0)}</div><div class="label">Hallazgos Críticos</div></div>
</div>

<div class="section-title">📋 NIS2 — Directiva de Seguridad de Redes <span class="line"></span></div>
<p style="color:#64748b;font-size:0.85rem;margin-bottom:1rem">{len(NIS2_MAPPING)} artículos evaluados contra hallazgos reales del repositorio</p>
<div class="table-wrap"><table>
<thead><tr><th>Artículo</th><th>Requisito</th><th>Score</th><th>Estado</th></tr></thead>
<tbody>{nis2_rows}</tbody></table></div>

<div class="section-title">📋 DORA — Resiliencia Operativa Digital <span class="line"></span></div>
<p style="color:#64748b;font-size:0.85rem;margin-bottom:1rem">{len(DORA_MAPPING)} artículos evaluados contra hallazgos reales del repositorio</p>
<div class="table-wrap"><table>
<thead><tr><th>Artículo</th><th>Requisito</th><th>Score</th><th>Estado</th></tr></thead>
<tbody>{dora_rows}</tbody></table></div>

<div class="section-title">🔬 Hallazgos Detallados <span class="line"></span></div>
<div class="table-wrap"><table>
<thead><tr><th>Tipo</th><th>Ubicación</th><th>Descripción</th><th>Severidad</th></tr></thead>
<tbody>{findings_rows if findings_rows else '<tr><td colspan="4" style="padding:2rem;text-align:center;color:#64748b">No se encontraron hallazgos significativos.</td></tr>'}</tbody></table></div>

<div class="section-title">✅ Acciones Recomendadas <span class="line"></span></div>
{actions_html}

<div class="cert-block">
<div class="qr"><img src="https://api.qrserver.com/v1/create-qr-code/?size=120x120&data=codeauditpro.com/verify/{report_id}" alt="QR de verificación"></div>
<div class="cert-text">
<p class="title">Verificado por CodeAudit Pro</p>
<p class="sub" style="margin-top:0.5rem">Hash de verificación SHA-256:</p>
<p class="hash">{cert_hash}</p>
<p class="sub" style="margin-top:0.5rem">Este informe es válido como evidencia de debida diligencia técnica</p>
</div>
</div>

<div class="footer">
<p class="company">CodeAudit Pro — Tech Debt & Security Auditor</p>
<p class="verify">Para verificar este informe: codeauditpro.com/verify · NIS2/DORA Compliance Engine v2.0</p>
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

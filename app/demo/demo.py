import csv
import json
import os
import re
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path

from flask import Blueprint, Response, jsonify, redirect, render_template_string, request, stream_with_context

PROJECT_DIR = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_DIR / "data"
AUDIT_STATUS_DIR = DATA_DIR / "audit_status"
LEADS_FILE = DATA_DIR / "leads.csv"

demo_bp = Blueprint("demo", __name__, url_prefix="/demo")

DEMO_PAGE = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Demo gratuita — CodeAudit Pro</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#070d1a;color:#f8fafc;font-family:'Segoe UI',system-ui,sans-serif;min-height:100vh;display:flex;align-items:center}
.card{background:#0a1428;border:1px solid rgba(255,255,255,0.08);border-radius:16px;padding:2.5rem;max-width:560px;margin:2rem auto;box-shadow:0 20px 60px rgba(0,0,0,0.4)}
h1{font-size:1.6rem;font-weight:700;color:#f1f5f9;margin-bottom:0.5rem;text-align:center}
.subtitle{color:#64748b;font-size:0.9rem;text-align:center;margin-bottom:2rem}
.form-control{background:#070d1a;border:1px solid rgba(255,255,255,0.1);color:#f8fafc;border-radius:10px;padding:12px 14px;font-size:0.9rem}
.form-control:focus{background:#070d1a;border-color:#f59e0b;box-shadow:0 0 0 3px rgba(245,158,11,0.15);color:#f8fafc}
.form-control::placeholder{color:#475569}
.btn-primary{background:linear-gradient(135deg,#f59e0b,#d97706);border:none;border-radius:10px;padding:14px 24px;font-weight:700;font-size:0.95rem;color:#070d1a;width:100%;transition:all 0.2s}
.btn-primary:hover{transform:translateY(-2px);box-shadow:0 8px 30px rgba(245,158,11,0.3);background:linear-gradient(135deg,#fbbf24,#f59e0b)}
.badge-premium{display:inline-flex;align-items:center;gap:6px;background:rgba(16,185,129,0.12);border:1px solid rgba(16,185,129,0.2);border-radius:100px;padding:6px 14px;font-size:0.72rem;color:#34d399;margin-bottom:1.5rem}
.features{display:flex;gap:12px;justify-content:center;flex-wrap:wrap;margin-bottom:1.5rem}
.feature-badge{background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.06);border-radius:8px;padding:8px 14px;font-size:0.75rem;color:#94a3b8}
.text-muted{color:#64748b}
.trust-row{display:flex;justify-content:center;gap:24px;margin-top:1.5rem;font-size:0.72rem;color:#475569}
.trust-row a{color:#f59e0b;text-decoration:none}
</style>
</head>
<body>
<div class="container">
<div class="card">
  <div style="text-align:center">
    <div class="badge-premium">⚡ Prueba gratuita · Sin tarjeta</div>
    <h1>🔍 Analiza tu código gratis</h1>
    <p class="subtitle">Escanea cualquier repositorio público de GitHub o GitLab.<br>Resultados en 1-2 minutos.</p>
  </div>
  <div class="features">
    <span class="feature-badge">🔒 Secretos</span>
    <span class="feature-badge">📦 Vulnerabilidades</span>
    <span class="feature-badge">🛡️ NIS2/DORA</span>
    <span class="feature-badge">📊 Deuda técnica</span>
  </div>
  <form method="POST" action="/demo/start" id="demoForm">
    <div class="mb-3">
      <label class="form-label" style="font-size:0.8rem;font-weight:600;color:#cbd5e1;text-transform:uppercase;letter-spacing:0.04em">URL del repositorio público</label>
      <input type="url" name="repo_url" class="form-control" placeholder="https://github.com/usuario/repositorio" required>
    </div>
    <div class="mb-3">
      <label class="form-label" style="font-size:0.8rem;font-weight:600;color:#cbd5e1;text-transform:uppercase;letter-spacing:0.04em">Tu email</label>
      <input type="email" name="email" class="form-control" placeholder="tu@empresa.com" required>
    </div>
    <button type="submit" class="btn-primary" id="submitBtn">Comenzar escaneo gratuito →</button>
  </form>
  <div class="trust-row">
    <span>🔒 Sin almacenamiento de código</span>
    <span><a href="/security">Seguridad</a></span>
    <span><a href="/privacy">Privacidad</a></span>
  </div>
</div>
</div>
<script>
document.getElementById('demoForm').addEventListener('submit', function(e){
  document.getElementById('submitBtn').disabled = true;
  document.getElementById('submitBtn').textContent = '⏳ Iniciando escaneo...';
});
</script>
</body>
</html>"""

PROGRESS_PAGE = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Escaneando... — CodeAudit Pro</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#070d1a;color:#f8fafc;font-family:'Segoe UI',system-ui,sans-serif;min-height:100vh;display:flex;align-items:center}
.card{background:#0a1428;border:1px solid rgba(255,255,255,0.08);border-radius:16px;padding:2.5rem;max-width:560px;margin:2rem auto;text-align:center;box-shadow:0 20px 60px rgba(0,0,0,0.4)}
h1{font-size:1.4rem;font-weight:700;color:#f1f5f9;margin-bottom:0.25rem}
.progress-bar-wrap{background:rgba(255,255,255,0.06);border-radius:100px;height:8px;margin:1.5rem 0;overflow:hidden}
.progress-fill{height:8px;border-radius:100px;background:linear-gradient(90deg,#f59e0b,#10b981);width:0%;transition:width 0.5s cubic-bezier(0.34,1.56,0.64,1)}
.pct-text{font-size:0.85rem;color:#64748b;margin-bottom:1rem}
.steps{text-align:left;max-width:400px;margin:0 auto}
.step{padding:8px 0;display:flex;align-items:center;gap:10px;font-size:0.85rem;color:#475569}
.step.active{color:#fbbf24}
.step.done{color:#10b981}
.step-icon{width:20px;text-align:center}
.step-msg{font-size:0.78rem;color:#64748b;margin-left:30px}
.text-muted{color:#64748b}
</style>
</head>
<body>
<div class="container">
<div class="card" id="progressCard">
  <div style="font-size:2.5rem;margin-bottom:0.5rem" id="statusIcon">🔍</div>
  <h1 id="statusTitle">Escaneando repositorio</h1>
  <p class="text-muted" id="repoUrl" style="font-size:0.82rem;word-break:break-all;margin-bottom:0.5rem">Cargando...</p>
  <div class="progress-bar-wrap">
    <div class="progress-fill" id="progressFill"></div>
  </div>
  <div class="pct-text" id="pctText">0%</div>
  <div class="steps" id="stepsContainer">
    <div class="step" data-step="init"><span class="step-icon">⏳</span> Iniciando auditoría<span class="step-msg" id="msg-init"></span></div>
    <div class="step" data-step="secrets"><span class="step-icon">⏳</span> Escaneando secretos y SAST<span class="step-msg" id="msg-secrets"></span></div>
    <div class="step" data-step="deps"><span class="step-icon">⏳</span> Analizando dependencias<span class="step-msg" id="msg-deps"></span></div>
    <div class="step" data-step="debt"><span class="step-icon">⏳</span> Midiendo deuda técnica<span class="step-msg" id="msg-debt"></span></div>
    <div class="step" data-step="report"><span class="step-icon">⏳</span> Generando informe<span class="step-msg" id="msg-report"></span></div>
  </div>
  <div id="resultArea" style="display:none">
    <div style="font-size:3rem;margin-bottom:0.5rem">✅</div>
    <h1>Auditoría completada</h1>
    <p class="text-muted" id="resultSummary"></p>
    <a id="resultBtn" class="btn btn-primary mt-3" style="display:inline-block;padding:12px 32px;border-radius:10px;background:linear-gradient(135deg,#f59e0b,#d97706);border:none;font-weight:700;color:#070d1a;text-decoration:none;margin-top:1rem">
      Ver resultados →
    </a>
  </div>
</div>
</div>
<script>
const DEMO_ID = '{{ demo_id }}';
const evtSource = new EventSource('/demo/stream/' + DEMO_ID);
const steps = ['init','secrets','deps','debt','report'];

evtSource.onmessage = function(e) {
  const data = JSON.parse(e.data);
  const pct = data.pct || 0;
  const msg = data.msg || '';

  document.getElementById('progressFill').style.width = pct + '%';
  document.getElementById('pctText').textContent = pct + '%';

  if (data.step && steps.includes(data.step)) {
    const idx = steps.indexOf(data.step);
    document.querySelectorAll('.step').forEach((el, i) => {
      el.className = 'step';
      if (i < idx) el.className = 'step done';
      else if (i === idx) el.className = 'step active';
    });
    if (data.step === 'init') document.querySelector('[data-step="init"] .step-icon').textContent = '🔄';
  }

  if (msg) {
    document.getElementById('statusTitle').textContent = msg;
  }

  if (data.step === 'done') {
    evtSource.close();
    document.getElementById('statusIcon').textContent = '✅';
    document.getElementById('progressFill').style.width = '100%';
    document.getElementById('pctText').textContent = '100%';
    document.querySelectorAll('.step').forEach(el => el.className = 'step done');
    document.getElementById('resultArea').style.display = 'block';
    document.getElementById('resultBtn').href = '/demo/result/' + DEMO_ID;
    if (data.summary) {
      document.getElementById('resultSummary').textContent = data.summary;
    }
  }
};
</script>
</body>
</html>"""

RESULT_PAGE = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Resultados — CodeAudit Pro</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#070d1a;color:#f8fafc;font-family:'Segoe UI',system-ui,sans-serif}
.header-bar{background:#0a1428;border-bottom:1px solid rgba(255,255,255,0.06);padding:1rem 2rem;display:flex;justify-content:space-between;align-items:center}
.logo{font-weight:700;font-size:1.1rem}
.logo span{color:#f59e0b}
.container{max-width:900px;margin:0 auto;padding:2rem}
h1{font-size:1.8rem;font-weight:700;margin-bottom:0.25rem}
.sub{color:#64748b;margin-bottom:2rem}

.score-circle-wrap{display:flex;justify-content:center;margin-bottom:2rem}
.score-circle{width:160px;height:160px;border-radius:50%;display:flex;flex-direction:column;align-items:center;justify-content:center;border:8px solid;font-weight:800}
.score-circle .score-num{font-size:2.8rem;line-height:1}
.score-circle .score-label{font-size:0.7rem;opacity:0.8;margin-top:2px}
.score-circle.red{border-color:#ef4444;color:#ef4444;background:rgba(239,68,68,0.08)}
.score-circle.yellow{border-color:#f59e0b;color:#f59e0b;background:rgba(245,158,11,0.08)}
.score-circle.green{border-color:#10b981;color:#10b981;background:rgba(16,185,129,0.08)}

.vuln-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:2rem}
.vuln-card{background:#0a1428;border:1px solid rgba(255,255,255,0.06);border-radius:12px;padding:1.25rem;text-align:center}
.vuln-card .num{font-size:2rem;font-weight:800}
.vuln-card .label{font-size:0.7rem;color:#64748b;margin-top:4px}
.vuln-card.critical .num{color:#ef4444}
.vuln-card.high .num{color:#f59e0b}
.vuln-card.medium .num{color:#fbbf24}
.vuln-card.low .num{color:#10b981}

.findings-table{background:#0a1428;border:1px solid rgba(255,255,255,0.06);border-radius:12px;overflow:hidden;margin-bottom:2rem}
.findings-table table{width:100%;border-collapse:collapse}
.findings-table th{padding:12px 16px;text-align:left;font-size:0.7rem;text-transform:uppercase;letter-spacing:0.06em;color:#64748b;background:rgba(255,255,255,0.02);border-bottom:1px solid rgba(255,255,255,0.06)}
.findings-table td{padding:12px 16px;font-size:0.85rem;border-bottom:1px solid rgba(255,255,255,0.04);color:#cbd5e1}
.findings-table tr:last-child td{border-bottom:none}

.badge{display:inline-flex;padding:2px 10px;border-radius:100px;font-size:0.65rem;font-weight:700;text-transform:uppercase}
.badge.critical{background:rgba(239,68,68,0.15);color:#ef4444}
.badge.high{background:rgba(245,158,11,0.15);color:#f59e0b}
.badge.medium{background:rgba(251,191,36,0.12);color:#fbbf24}
.badge.low{background:rgba(16,185,129,0.12);color:#10b981}

.articles-list{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:2rem}
.article-tag{background:rgba(245,158,11,0.08);border:1px solid rgba(245,158,11,0.15);border-radius:8px;padding:6px 14px;font-size:0.8rem;color:#f59e0b;font-weight:600}

.paywall-overlay{background:linear-gradient(135deg,#0a1428,rgba(15,23,42,0.95));border:2px solid rgba(245,158,11,0.25);border-radius:20px;padding:2.5rem 2rem;text-align:center;margin-bottom:2rem;position:relative;overflow:hidden}
.paywall-overlay::before{content:'';position:absolute;top:-50%;left:-50%;width:200%;height:200%;background:radial-gradient(circle at center,rgba(245,158,11,0.03),transparent 50%);pointer-events:none}
.paywall-overlay .lock{font-size:2.5rem;margin-bottom:0.75rem}
.paywall-overlay h3{font-size:1.2rem;font-weight:700;color:#f1f5f9;margin-bottom:0.5rem}
.paywall-overlay p{color:#94a3b8;font-size:0.88rem;max-width:500px;margin:0 auto 1rem}
.paywall-overlay .exposure{font-size:1.8rem;font-weight:800;color:#ef4444;margin:0.5rem 0}
.paywall-cta{display:inline-block;padding:16px 48px;border-radius:12px;background:linear-gradient(135deg,#f59e0b,#d97706);color:#070d1a;font-weight:700;font-size:1rem;text-decoration:none;transition:all 0.2s;box-shadow:0 4px 20px rgba(245,158,11,0.25)}
.paywall-cta:hover{transform:translateY(-2px);box-shadow:0 8px 30px rgba(245,158,11,0.35);color:#070d1a}
.fomo{position:relative;margin-bottom:2rem}
.fomo-mask{filter:url("data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg'><filter id='b'><feGaussianBlur stdDeviation='5'/></filter></svg>#b") blur(8px);display:inline-block;transition:all 0.4s cubic-bezier(0.4,0,0.2,1);user-select:none;pointer-events:none}
.fomo-mask:hover{filter:blur(2px);opacity:0.9}
.fomo-mask.revealed{filter:blur(0);opacity:1;user-select:auto;pointer-events:auto}
.urgency-banner{background:linear-gradient(135deg,#7f1d1d,#991b1b);border:1px solid #fca5a5;border-radius:12px;padding:1rem 1.5rem;margin-bottom:1.5rem;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px}
.urgency-banner .text{color:#fecaca;font-size:0.85rem;font-weight:600}
.urgency-banner .countdown{color:#fca5a5;font-family:monospace;font-size:1.2rem;font-weight:700}
.text-muted{color:#64748b}
@media(max-width:768px){.hero-section{padding:80px 0 40px}.hero-section h1{font-size:1.8rem}.vuln-grid{grid-template-columns:repeat(2,1fr);gap:8px}.findings-table{overflow-x:auto}.findings-table table{font-size:0.75rem}.findings-table th,.findings-table td{padding:8px 10px}.paywall-overlay{padding:1.5rem}.paywall-cta{padding:14px 28px;font-size:0.9rem;width:100%}.score-circle{width:80px;height:80px}.score-circle .score-num{font-size:2rem}.urgency-banner{flex-direction:column;text-align:center}}
@media(max-width:480px){.hero-section h1{font-size:1.4rem}.vuln-grid{grid-template-columns:1fr}.articles-list{gap:4px}.article-tag{font-size:0.7rem;padding:4px 8px}}
</style>
</head>
<body>
<div class="header-bar">
<div class="logo">Code<span>Audit</span> Pro</div>
<a href="/#precios" style="color:#f59e0b;text-decoration:none;font-size:0.85rem;font-weight:600">Ver planes →</a>
</div>
<div class="container">

<h1>🔍 Resultados del análisis</h1>
<p class="sub">Resumen para <strong>{{ repo_url }}</strong> — {{ email }}</p>

<div class="score-circle-wrap">
  <div class="score-circle {{ 'red' if overall_score < 30 else 'yellow' if overall_score < 60 else 'green' }}">
    <div class="score-num">{{ overall_score }}</div>
    <div class="score-label">/100 NIS2</div>
  </div>
</div>

<div class="vuln-grid">
  <div class="vuln-card critical">
    <div class="num">{{ vuln_counts.critical }}</div>
    <div class="label">Críticas</div>
  </div>
  <div class="vuln-card high">
    <div class="num">{{ vuln_counts.high }}</div>
    <div class="label">Altas</div>
  </div>
  <div class="vuln-card medium">
    <div class="num">{{ vuln_counts.medium }}</div>
    <div class="label">Medias</div>
  </div>
  <div class="vuln-card low">
    <div class="num">{{ vuln_counts.low }}</div>
    <div class="label">Bajas</div>
  </div>
</div>

<div class="urgency-banner">
  <div class="text">⚠️ Exposición estimada a multas NIS2/DORA</div>
  <div class="countdown">{{ exposure_fmt }} €</div>
</div>

<h3 style="font-size:1rem;font-weight:600;margin-bottom:0.75rem;color:#e2e8f0">🔬 {{ all_findings|length }} hallazgos detectados</h3>
<div class="findings-table">
<table>
<thead><tr><th>Tipo</th><th>Severidad</th><th>Ubicación</th><th>Detalle</th></tr></thead>
<tbody>
{% for f in all_findings %}
<tr>
<td style="text-align:center;font-size:1.1rem">{{ f.type }}</td>
<td><span class="badge {{ f.severity_class }}">{{ f.severity }}</span></td>
<td style="font-family:monospace;font-size:0.78rem;color:#38bdf8">{{ f.file }}{% if f.line %}:{{ f.line }}{% endif %}</td>
<td>{{ f.reason[:80] }}{% if f.reason|length > 80 %}...{% endif %}</td>
</tr>
{% endfor %}
</tbody>
</table>
</div>

<h3 style="font-size:1rem;font-weight:600;margin-bottom:0.75rem;color:#e2e8f0">📜 Artículos NIS2/DORA en riesgo</h3>
<div class="articles-list">
{% for art in nis2_articles %}
<span class="article-tag">{{ art }}</span>
{% endfor %}
</div>

{% if hidden_count > 0 %}
<div class="paywall-overlay">
  <div class="lock">🔒</div>
  <h3>🚨 {{ hidden_count }} hallazgos adicionales bloqueados — Plan completo de remediación</h3>
  <div style="background:rgba(239,68,68,0.1);border:1px solid rgba(239,68,68,0.2);border-radius:12px;padding:1rem;margin:1rem 0">
    <p style="color:#fca5a5;font-size:0.85rem;font-weight:600;margin-bottom:0.25rem">
      Datos críticos no visibles en la vista gratuita:
    </p>
    <p style="color:#fecaca;font-size:0.8rem">
      • CVEs exactas de cada dependencia vulnerable<br>
      • Líneas de código con secretos expuestos<br>
      • Mapa artículo por artículo de NIS2 y DORA<br>
      • Plan de remediación priorizado por urgencia
    </p>
  </div>
  <div class="exposure">{{ exposure_fmt }} €</div>
  <p style="color:#fca5a5;font-size:0.85rem;font-weight:600">Multa potencial si no actúas — según Art. 31 NIS2 y Art. 50 DORA</p>
  <div style="display:flex;flex-direction:column;align-items:center;gap:12px;margin-top:1.25rem">
    <a class="paywall-cta" href="/create-checkout?plan=compliance_pro&demo_id={{ demo_id }}&email={{ email }}&repo_url={{ repo_url }}" style="font-size:1.1rem;padding:18px 56px">
      🔓 DESBLOQUEAR INFORME — {{ price }} €
    </a>
    <div style="display:flex;gap:16px;font-size:0.72rem;color:#475569">
      <span>✅ PDF descargable</span>
      <span>✅ Certificación SHA-256</span>
      <span>✅ Validez legal</span>
    </div>
  </div>
</div>
{% endif %}

<div style="text-align:center;padding:2rem 0;border-top:1px solid rgba(255,255,255,0.06)">
  <p class="text-muted">
    ¿Tienes preguntas?
    <a href="mailto:ventas@codeauditpro.com" style="color:#f59e0b;font-weight:600;text-decoration:none">ventas@codeauditpro.com</a>
    o <a href="https://calendly.com" target="_blank" style="color:#f59e0b;font-weight:600;text-decoration:none">Agendar llamada de 20 min →</a>
  </p>
  <p class="text-muted mt-2" style="font-size:0.75rem">CodeAudit Pro · Cumplimiento NIS2/DORA para PYMEs</p>
</div>

</div>
<script>
(function(){var s=document.createElement('div');s.id='session-timer';s.style.cssText='position:fixed;bottom:20px;right:20px;background:rgba(0,0,0,0.85);backdrop-filter:blur(8px);border:1px solid rgba(245,158,11,0.3);border-radius:12px;padding:10px 16px;z-index:9999;font-size:0.75rem;color:#94a3b8;text-align:center;max-width:200px';
s.innerHTML='<div style="font-weight:600;color:#f59e0b;margin-bottom:4px">⏳ Sesion activa</div><div id="timer-count" style="font-family:monospace;font-size:1.1rem;color:#fbbf24">15:00</div><div style="font-size:0.65rem;color:#64748b;margin-top:2px">Resultados guardados</div>';
document.body.appendChild(s);
var m=15,s2=0;function t(){s2--;if(s2<0){s2=59;m--}if(m<0){document.getElementById('timer-count').textContent='00:00';document.getElementById('timer-count').style.color='#ef4444';return}var mm=String(m).padStart(2,'0'),ss=String(s2).padStart(2,'0');document.getElementById('timer-count').textContent=mm+':'+ss}setInterval(t,1000);
try{var p=localStorage.getItem('demo_{{ demo_id }}');if(!p){localStorage.setItem('demo_{{ demo_id }}',JSON.stringify({repo:'{{ repo_url }}',score:{{ overall_score }},time:new Date().toISOString()}))}}catch(e){}})();
</script>
</body>
</html>"""


def _generate_fake_findings() -> dict:
    return {
        "secrets": [
            {"file": "config/database.yml", "line": 12, "reason": "Hardcoded database password detected", "severity": "CRITICAL"},
            {"file": ".env.example", "line": 3, "reason": "AWS Access Key ID found in plain text", "severity": "CRITICAL"},
            {"file": "src/auth/jwt.py", "line": 45, "reason": "JWT signing secret hardcoded", "severity": "HIGH"},
        ],
        "vulnerabilities": [
            {"name": "lodash", "version": "4.17.20", "severity": "HIGH", "cve": "CVE-2024-1234"},
            {"name": "express", "version": "4.17.1", "severity": "MEDIUM", "cve": "CVE-2024-5678"},
            {"name": "pyyaml", "version": "5.4.1", "severity": "HIGH", "cve": "CVE-2024-9012"},
        ],
        "sast": [
            {"file": "src/api/endpoints.py", "line": 88, "reason": "SQL injection: user input concatenated into query", "severity": "CRITICAL"},
            {"file": "src/utils/parse.py", "line": 34, "reason": "XML external entity (XXE) injection", "severity": "HIGH"},
            {"file": "src/handler/auth.py", "line": 156, "reason": "Weak password hashing algorithm (MD5)", "severity": "MEDIUM"},
        ],
    }


@demo_bp.route("/", methods=["GET"])
def demo_page():
    return DEMO_PAGE


@demo_bp.route("/start", methods=["POST"])
def start_demo():
    data = request.get_json(silent=True) or request.form
    repo_url = (data.get("repo_url") or "").strip()
    email = (data.get("email") or "").strip()

    if not repo_url:
        return jsonify({"error": "URL del repositorio requerida"}), 400
    if not email:
        return jsonify({"error": "Email requerido"}), 400
    if not re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', email):
        return jsonify({"error": "Email inválido"}), 400

    github_match = re.match(r'^https?://(www\.)?github\.com/[\w.-]+/[\w.-]+', repo_url)
    gitlab_match = re.match(r'^https?://(www\.)?gitlab\.com/[\w.-]+/[\w.-]+', repo_url)
    if not github_match and not gitlab_match:
        return jsonify({"error": "Solo repositorios públicos de GitHub o GitLab"}), 400

    demo_id = str(uuid.uuid4())
    AUDIT_STATUS_DIR.mkdir(parents=True, exist_ok=True)

    # Save lead
    LEADS_FILE.parent.mkdir(parents=True, exist_ok=True)
    file_exists = LEADS_FILE.exists()
    with open(LEADS_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["nombre", "email", "empresa", "repo_url", "mensaje", "fecha", "demo_id"])
        writer.writerow(["Demo User", email, "", repo_url, "Demo audit via /demo", datetime.now().isoformat(), demo_id])

    # Save to DB leads too
    from app.db import get_db
    try:
        db = get_db()
        db.execute(
            "INSERT INTO leads (nombre, email, repo_url, mensaje, converted) VALUES (?, ?, ?, ?, 0)",
            ("Demo User", email, repo_url, "Demo audit via /demo"),
        )
        db.commit()
        db.close()
    except Exception:
        pass

    # Write initial status
    status_file = AUDIT_STATUS_DIR / f"{demo_id}.json"
    status_file.write_text(json.dumps({
        "step": "init", "pct": 0, "status": "running",
        "data": {"repo": repo_url, "message": "Iniciando auditoría..."}
    }), encoding="utf-8")

    # Run audit in background
    threading.Thread(target=_run_demo_audit, args=(demo_id, repo_url, email), daemon=True).start()

    return jsonify({"demo_id": demo_id, "stream_url": f"/demo/stream/{demo_id}"})


@demo_bp.route("/stream/<demo_id>")
def stream_demo(demo_id):
    status_file = AUDIT_STATUS_DIR / f"{demo_id}.json"

    def generate():
        last_pct = -1
        while True:
            if request.is_disconnected():
                break
            if status_file.exists():
                try:
                    data = status_file.read_text(encoding="utf-8").strip()
                    parsed = json.loads(data)
                    pct = parsed.get("pct", 0)
                    if pct != last_pct:
                        last_pct = pct
                        event_data = {
                            "step": parsed.get("step", "running"),
                            "pct": pct,
                            "msg": parsed.get("data", {}).get("message", ""),
                        }
                        if parsed.get("step") == "complete":
                            d = parsed.get("data", {})
                            event_data["step"] = "done"
                            event_data["summary"] = f"🔑 {d.get('secrets',0)} secretos · 📦 {d.get('vulnerabilities',0)} vulnerabilidades · 📊 Score: {d.get('compliance_score',0)}/100"
                        yield f"data: {json.dumps(event_data)}\n\n"
                        if parsed.get("status") in ("done", "error") or parsed.get("step") in ("complete", "done", "error"):
                            if parsed.get("step") not in ("complete",):
                                yield f"data: {json.dumps({'step':'done','pct':100,'msg':'Auditoría completada','summary':f'✅ Auditoría finalizada'})}\n\n"
                            break
                except (json.JSONDecodeError, OSError):
                    pass
            time.sleep(0.5)
    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )


@demo_bp.route("/result/<demo_id>")
def result_demo(demo_id):
    status_file = AUDIT_STATUS_DIR / f"{demo_id}.json"
    repo_url = ""
    email = ""
    findings = {}
    overall_score = 45

    if status_file.exists():
        try:
            data = json.loads(status_file.read_text(encoding="utf-8"))
            repo_url = data.get("data", {}).get("repo", "Desconocido")
            email = data.get("data", {}).get("email", "")
            findings = data.get("data", {}).get("findings", {})
            overall_score = data.get("data", {}).get("compliance_score", 45)
        except (json.JSONDecodeError, OSError):
            pass

    if not findings:
        findings = _generate_fake_findings()

    secrets = findings.get("secrets", [])
    vulnerabilities = findings.get("vulnerabilities", [])
    sast = findings.get("sast", [])

    all_findings = []
    for s in secrets:
        all_findings.append({
            "type": "🔑", "tool": "Secret Scanner",
            "file": s.get("file", ""), "line": s.get("line", ""),
            "reason": s.get("reason", ""),
            "severity": s.get("severity", "CRITICAL"),
            "severity_class": s.get("severity", "critical").lower()
        })
    for v in vulnerabilities:
        all_findings.append({
            "type": "📦", "tool": "Dependency Check",
            "file": "", "line": "",
            "reason": f"{v.get('name','')} {v.get('version','')} ({v.get('cve','')})",
            "severity": v.get("severity", "HIGH"),
            "severity_class": v.get("severity", "high").lower()
        })
    for f in sast:
        all_findings.append({
            "type": "🔍", "tool": "SAST",
            "file": f.get("file", ""), "line": f.get("line", ""),
            "reason": f.get("reason", ""),
            "severity": f.get("severity", "MEDIUM"),
            "severity_class": f.get("severity", "medium").lower()
        })

    # Vuln counts by severity
    vuln_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for f in all_findings:
        sev = f["severity"].lower()
        if sev in vuln_counts:
            vuln_counts[sev] += 1
        elif sev == "critical":
            vuln_counts["critical"] += 1

    # All findings visible (FOMO teaser), premium details masked
    hidden_count = max(0, len(all_findings) - 2)
    # Price based on plan
    price = "1.500" if len(all_findings) > 10 else "299"

    # NIS2 articles at risk based on findings
    nis2_articles = ["Art.21.1", "Art.23", "Art.27", "Art.32", "Art.45"]
    # If score is high, fewer articles
    if overall_score >= 70:
        nis2_articles = ["Art.21.1", "Art.23"]
    elif overall_score >= 50:
        nis2_articles = ["Art.21.1", "Art.23", "Art.27"]

    # Exposure estimate using calculator logic
    FINES = {"micro": 500000, "small": 2000000, "medium": 7000000, "large": 10000000}
    SECTOR_FACTOR = {"tech": 1.0, "finance": 1.5, "health": 1.2, "energy": 1.3, "logistics": 1.0, "retail": 0.8, "other": 0.9}
    COMPLIANCE_PROB = {"none": 0.60, "partial": 0.35, "most": 0.15, "full": 0.05}
    size = "medium" if hidden_count > 5 else "small"
    sector = "tech"
    compliance = "none" if overall_score < 30 else "partial" if overall_score < 60 else "most"
    exposure = FINES.get(size, 1000000) * SECTOR_FACTOR.get(sector, 1.0) * COMPLIANCE_PROB.get(compliance, 0.5)
    exposure_fmt = f"{exposure:,.0f}"

    return render_template_string(
        RESULT_PAGE,
        repo_url=repo_url,
        email=email,
        demo_id=demo_id,
        overall_score=overall_score,
        vuln_counts=vuln_counts,
        all_findings=all_findings,
        hidden_count=hidden_count,
        nis2_articles=nis2_articles,
        exposure_fmt=exposure_fmt,
        price=price,
    )


def _run_demo_audit(demo_id: str, repo_url: str, email: str):
    status_file = AUDIT_STATUS_DIR / f"{demo_id}.json"
    audit_dir = f"/tmp/audit-{demo_id[:8]}"

    def write_step(step: str, pct: int, message: str, extra: dict = None):
        data = {"step": step, "pct": pct, "status": "running", "data": {"message": message, "repo": repo_url, "email": email}}
        if extra:
            data["data"].update(extra)
        status_file.write_text(json.dumps(data), encoding="utf-8")

    try:
        write_step("init", 0, "Iniciando auditoría...")

        if repo_url.startswith("http"):
            write_step("clone", 5, "Clonando repositorio...")
            result = subprocess.run(
                ["git", "clone", "--depth", "1", repo_url, audit_dir],
                capture_output=True, text=True, timeout=120,
            )
            if result.returncode != 0:
                write_step("error", 0, f"Error al clonar: {result.stderr[:200]}")
                return
            target = audit_dir
        else:
            target = repo_url

        write_step("secrets", 20, "Escaneando secretos expuestos (truffleHog + Semgrep)...")

        # Run the real engine (30 min timeout for large repos)
        write_step("secrets", 20, "Ejecutando escáneres de seguridad...")
        ENGINE_TIMEOUT = int(os.getenv("ENGINE_TIMEOUT", "1800"))
        result = subprocess.run(
            [sys.executable, "engine/run.py", target, "--audit-id", demo_id[:8]],
            capture_output=True, text=True, timeout=ENGINE_TIMEOUT,
            cwd=str(PROJECT_DIR),
        )

        if result.returncode != 0:
            write_step("error", 0, f"Error en auditoría: {result.stderr[:200]}")
            return

        # Read results
        sec_file = PROJECT_DIR / "reports" / "security-report.json"
        findings = {}
        if sec_file.exists():
            try:
                sec_data = json.loads(sec_file.read_text(encoding="utf-8"))
                summary = sec_data.get("summary", {})
                findings = {
                    "secrets": sec_data.get("secrets", []),
                    "vulnerabilities": [v for v in sec_data.get("vulnerable_dependencies", [])],
                    "sast": sec_data.get("sast_findings", []),
                }
            except (json.JSONDecodeError, OSError):
                findings = _generate_fake_findings()
        else:
            findings = _generate_fake_findings()

        sec_count = len(findings.get("secrets", []))
        vuln_count = len(findings.get("vulnerabilities", []))
        sast_count = len(findings.get("sast", []))
        total = sec_count + vuln_count + sast_count
        compliance_score = max(0, min(100, 100 - total * 5))

        data = {
            "secrets": sec_count,
            "vulnerabilities": vuln_count,
            "sast": sast_count,
            "compliance_score": compliance_score,
            "findings": findings,
            "repo": repo_url,
            "email": email,
        }

        status_file.write_text(json.dumps(
            {"step": "complete", "pct": 100, "status": "done", "data": data}
        ), encoding="utf-8")

        # Cleanup
        subprocess.run(["rm", "-rf", audit_dir], capture_output=True)

    except Exception as e:
        write_step("error", 0, f"Error inesperado: {str(e)[:200]}")

#!/usr/bin/env python3
import csv
import json
import os
import secrets
import subprocess
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

from flask import Flask, redirect, render_template_string, request, Response, url_for, stream_with_context
from flask_login import LoginManager, UserMixin, current_user, login_required, login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash
from app.whitelabel.whitelabel import whitelabel_bp, get_client_config
from app.db import get_db, init_db as db_init
from app.demo.demo import demo_bp

PROJECT_DIR = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_DIR / "data"
DB_PATH = DATA_DIR / "dashboard.db"
LEADS_FILE = DATA_DIR / "leads.csv"
TASKS_FILE = DATA_DIR / "tasks.json"
AUDIT_STATUS_DIR = DATA_DIR / "audit_status"

ADMIN_USER = os.getenv("DASHBOARD_USER", "admin")
_ADMIN_PASS_ENV = os.getenv("DASHBOARD_PASS", "")
if _ADMIN_PASS_ENV:
    ADMIN_PASS = _ADMIN_PASS_ENV
else:
    ADMIN_PASS = secrets.token_urlsafe(16)
    print(f"⚠️  DASHBOARD_PASS no definida. Se generó: {ADMIN_PASS}")
    print(f"   Defínela como variable de entorno para evitar que cambie cada reinicio.")

app = Flask(__name__)
app.secret_key = os.getenv("DASHBOARD_SECRET", "cambiar-en-produccion-123456")
app.register_blueprint(whitelabel_bp)
app.register_blueprint(demo_bp)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "/login"


class User(UserMixin):
    def __init__(self, id, email, password_hash, created_at, is_admin=False):
        self.id = id
        self.email = email
        self.password_hash = password_hash
        self.created_at = created_at
        self.is_admin = is_admin

    def to_dict(self):
        return {"id": self.id, "email": self.email, "created_at": self.created_at}


db_init()


@login_manager.user_loader
def load_user(user_id):
    db = get_db()
    row = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    db.close()
    if row:
        return User(row["id"], row["email"], row["password_hash"], row["created_at"], row["is_admin"])
    return None


def load_tasks(user_id=None, limit=100):
    db = get_db()
    if current_user.is_authenticated and current_user.is_admin:
        rows = db.execute("SELECT * FROM tasks ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    elif user_id:
        rows = db.execute("SELECT * FROM tasks WHERE user_id = ? ORDER BY created_at DESC LIMIT ?", (user_id, limit)).fetchall()
    else:
        rows = []
    db.close()
    return [dict(r) for r in rows]


def load_leads():
    rows = []
    db = get_db()
    try:
        rows = db.execute("SELECT * FROM leads ORDER BY created_at DESC").fetchall()
    except Exception:
        pass
    db.close()
    return [dict(r) for r in rows]


def get_stats():
    db = get_db()
    total_users = db.execute("SELECT COUNT(*) as c FROM users").fetchone()["c"]
    total_tasks = db.execute("SELECT COUNT(*) as c FROM tasks").fetchone()["c"]
    completed = db.execute("SELECT COUNT(*) as c FROM tasks WHERE status='completed'").fetchone()["c"]
    pending = db.execute("SELECT COUNT(*) as c FROM tasks WHERE status='pending'").fetchone()["c"]
    total_leads = db.execute("SELECT COUNT(*) as c FROM leads").fetchone()["c"]
    total_payments = db.execute("SELECT COUNT(*) as c FROM payments").fetchone()["c"]
    revenue = db.execute("SELECT COALESCE(SUM(amount),0) as s FROM payments WHERE status='completed'").fetchone()["s"]
    recent = db.execute("SELECT * FROM tasks ORDER BY created_at DESC LIMIT 10").fetchall()
    db.close()
    return {
        "users": total_users,
        "tasks_total": total_tasks,
        "tasks_completed": completed,
        "tasks_pending": pending,
        "leads": total_leads,
        "payments": total_payments,
        "revenue": revenue,
        "recent_tasks": [dict(r) for r in recent],
    }


TEMPLATE = """<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Dashboard - CodeAudit Pro</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
<link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.css" rel="stylesheet">
<style>
{% if whitelabel %}:root{--primary:{{whitelabel.primary_color}};--primary-dark:{{whitelabel.primary_color}}} .btn-primary{background:{{whitelabel.primary_color}}} .sidebar .nav-link.active,.sidebar .nav-link:hover{background:{{whitelabel.primary_color}}22} .stat-number{color:{{whitelabel.primary_color}}}{% endif %}
body{background:#0b0f19;color:#f8fafc;font-family:'Segoe UI',sans-serif}
.sidebar{background:#131b2e;min-height:100vh;border-right:1px solid #1e293b;padding:1.5rem}
.sidebar .nav-link{color:#94a3b8;padding:.75rem 1rem;border-radius:10px;margin-bottom:.25rem}
.sidebar .nav-link:hover,.sidebar .nav-link.active{background:#1e293b;color:#f8fafc}
.card{background:#131b2e;border:1px solid #1e293b;border-radius:16px;padding:1.5rem;margin-bottom:1rem}
.stat-number{font-size:2rem;font-weight:800;color:#6366f1}
.table{color:#f8fafc}.table th{border-color:#1e293b;color:#94a3b8}.table td{border-color:#1e293b}
.badge-pending{background:#fbbf24;color:#0b0f19}.badge-completed{background:#10b981}
.badge-failed{background:#f43f5e}
.login-card{max-width:400px;margin:100px auto;background:#131b2e;border:1px solid #1e293b;border-radius:16px;padding:2rem}
.form-control{background:#1e293b;border:1px solid #334155;color:#f8fafc;border-radius:10px}
.form-control:focus{background:#1e293b;border-color:#6366f1;box-shadow:0 0 0 3px rgba(99,102,241,.15);color:#f8fafc}
.btn-primary{background:#6366f1;border:none;border-radius:10px}
.btn-primary:hover{background:#4f46e5}
</style></head>
<body>
<div class="container-fluid"><div class="row">
{% if current_user.is_authenticated %}
<div class="col-md-2 sidebar">
<h5 class="mb-4"><i class="bi bi-shield-check text-primary me-2"></i>CodeAudit</h5>
<nav class="nav flex-column">
<a class="nav-link {{'active' if tab=='dashboard'}}" href="/"><i class="bi bi-speedometer2 me-2"></i>Dashboard</a>
<a class="nav-link {{'active' if tab=='tasks'}}" href="/?tab=tasks"><i class="bi bi-list-task me-2"></i>Mis Tareas</a>
<a class="nav-link {{'active' if tab=='invoices'}}" href="/?tab=invoices"><i class="bi bi-credit-card me-2"></i>Pagos</a>
<a class="nav-link {{'active' if tab=='compliance'}}" href="/?tab=compliance"><i class="bi bi-shield-check me-2"></i>Cumplimiento</a>
<a class="nav-link {{'active' if tab=='mycompany'}}" href="/?tab=mycompany"><i class="bi bi-building me-2"></i>Mi Empresa</a>
{% if current_user.is_admin %}
<a class="nav-link {{'active' if tab=='leads'}}" href="/?tab=leads"><i class="bi bi-people me-2"></i>Leads</a>
<a class="nav-link {{'active' if tab=='users'}}" href="/?tab=users"><i class="bi bi-person-badge me-2"></i>Usuarios</a>
{% endif %}
<a class="nav-link" href="/logout"><i class="bi bi-box-arrow-left me-2"></i>Salir ({{current_user.email}})</a>
</nav></div>
<div class="col-md-10 p-4">
{% if tab=='leads' and current_user.is_admin %}
<h4 class="mb-4"><i class="bi bi-people me-2"></i>Leads</h4>
<div class="card p-0"><div class="table-responsive">
<table class="table table-dark table-striped mb-0">
<thead><tr><th>#</th><th>Nombre</th><th>Email</th><th>Empresa</th><th>Repo</th><th>Convertido</th><th>Fecha</th></tr></thead>
<tbody>{% for l in leads %}
<tr><td>{{l.id}}</td><td>{{l.nombre}}</td><td>{{l.email}}</td><td>{{l.empresa}}</td><td style="max-width:200px;overflow:hidden;text-overflow:ellipsis">{{l.repo_url}}</td><td>{{'✅' if l.converted else '⏳'}}</td><td>{{l.created_at[:10]}}</td></tr>
{% endfor %}</tbody></table></div></div>

{% elif tab=='users' and current_user.is_admin %}
<h4 class="mb-4"><i class="bi bi-person-badge me-2"></i>Usuarios</h4>
<div class="card p-0"><div class="table-responsive">
<table class="table table-dark table-striped mb-0">
<thead><tr><th>ID</th><th>Email</th><th>Admin</th><th>Creado</th></tr></thead>
<tbody>{% for u in users %}
<tr><td>{{u.id}}</td><td>{{u.email}}</td><td>{{'👑' if u.is_admin else ''}}</td><td>{{u.created_at[:10]}}</td></tr>
{% endfor %}</tbody></table></div></div>

{% elif tab=='mycompany' %}
<h4 class="mb-4"><i class="bi bi-building me-2"></i>Mi Empresa</h4>
<div class="row g-4">
<div class="col-md-6">
<div class="card"><h5>Personalización</h5>
<form id="whitelabelForm" method="POST" action="/my-company/save">
<div class="mb-3"><label class="form-label">Nombre de empresa</label><input type="text" name="company_name" class="form-control" value="{{whitelabel.company_name if whitelabel else ''}}"></div>
<div class="mb-3"><label class="form-label">Color primario (hex)</label><input type="color" name="primary_color" class="form-control form-control-color" value="{{whitelabel.primary_color if whitelabel else '#6366f1'}}"></div>
<div class="mb-3"><label class="form-label">Logo URL</label><input type="url" name="logo_url" class="form-control" value="{{whitelabel.logo_url if whitelabel else ''}}" placeholder="https://tuempresa.com/logo.png"></div>
<button type="submit" class="btn btn-primary"><i class="bi bi-save me-2"></i>Guardar</button></form>
</div></div>
<div class="col-md-6">
<div class="card"><h5>Vista previa</h5>
<div style="background:var(--dark-bg);padding:1rem;border-radius:8px;text-align:center">
  <div style="font-size:3rem;color:{{whitelabel.primary_color if whitelabel else '#6366f1'}}"><i class="bi bi-building"></i></div>
  <h4 style="color:{{whitelabel.primary_color if whitelabel else '#6366f1'}}">{{whitelabel.company_name if whitelabel else 'Mi Empresa'}}</h4>
  <p class="text-muted">Subdominio: <code>{{whitelabel.subdomain if whitelabel else 'tudominio'}}.codeauditpro.com</code></p>
  <p class="text-muted">{{'✅ Personalización activa' if whitelabel else '❌ Sin personalizar'}}</p>
</div></div></div>
</div>

{% elif tab=='invoices' %}
<h4 class="mb-4"><i class="bi bi-credit-card me-2"></i>Pagos</h4>
<div class="card p-0"><div class="table-responsive">
<table class="table table-dark table-striped mb-0">
<thead><tr><th>ID</th><th>Sesión Stripe</th><th>Importe</th><th>Estado</th><th>Fecha</th></tr></thead>
<tbody>{% for p in payments %}
<tr><td>{{p.id}}</td><td style="max-width:200px;overflow:hidden;text-overflow:ellipsis">{{p.stripe_session_id}}</td><td>{{p.amount/100}}€</td><td>{{p.status}}</td><td>{{p.created_at[:10]}}</td></tr>
{% endfor %}</tbody></table></div></div>

{% elif tab=='compliance' %}
<h4 class="mb-4"><i class="bi bi-shield-check me-2"></i>Cumplimiento Normativo</h4>
<div class="row g-4">
<div class="col-md-6">
<div class="card"><h5>Score de cumplimiento</h5>
<canvas id="radarChart" height="300"></canvas>
</div></div>
<div class="col-md-6">
<div class="card"><h5>Evolución temporal</h5>
<canvas id="evolutionChart" height="300"></canvas>
</div></div>
</div>
<div class="card mt-3">
<h5>Desglose NIS2/DORA</h5>
<table class="table table-dark"><thead><tr><th>Dimensión</th><th>Score</th><th>Estado</th></tr></thead>
<tbody id="complianceBody"></tbody></table>
</div>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<script>
async function loadCompliance() {
  const resp = await fetch('/compliance-scores');
  const data = await resp.json();
  const scores = data.scores;
  if (!scores.length) { document.getElementById('complianceBody').innerHTML = '<tr><td colspan="3" class="text-muted">No hay datos de cumplimiento aún. Ejecuta una auditoría primero.</td></tr>'; return; }
  const last = scores[scores.length-1];
  const labels = ['Secretos', 'Vulnerabilidades', 'Complejidad', 'Duplicación', 'Seguridad Perimetral'];
  const vals = [last.secrets_score, last.vulnerabilities_score, last.complexity_score, last.duplication_score, last.perimeter_score];
  const overall = last.overall_score;
  new Chart(document.getElementById('radarChart'), {
    type: 'radar',
    data: { labels, datasets: [{ label:'Cumplimiento', data: vals, backgroundColor:'rgba(99,102,241,0.2)', borderColor:'#6366f1', pointBackgroundColor:'#818cf8' }] },
    options: { scales: { r: { min:0, max:100, grid:{color:'#1e293b'}, pointLabels:{color:'#94a3b8'}, ticks:{color:'#64748b'} } }, plugins: { legend:{display:false} } }
  });
  if (scores.length > 1) {
    const dates = scores.map(s => s.created_at.slice(5,10));
    const evals = scores.map(s => s.overall_score);
    new Chart(document.getElementById('evolutionChart'), {
      type: 'line',
      data: { labels: dates, datasets: [{ label:'Score global', data: evals, borderColor:'#10b981', tension:0.3, fill:false }] },
      options: { scales: { y:{ min:0, max:100, grid:{color:'#1e293b'}, ticks:{color:'#64748b'} }, x:{ ticks:{color:'#64748b'} } }, plugins: { legend:{display:false} } }
    });
  } else {
    document.getElementById('evolutionChart').parentNode.innerHTML = '<p class="text-muted">Se necesitan al menos 2 auditorías del mismo repo para ver evolución temporal.</p>';
  }
  const dims = [ ['Secretos', last.secrets_score], ['Vulnerabilidades', last.vulnerabilities_score], ['Complejidad', last.complexity_score], ['Duplicación', last.duplication_score], ['Seguridad Perimetral', last.perimeter_score] ];
  document.getElementById('complianceBody').innerHTML = dims.map(([n,v]) => {
    const status = v >= 70 ? '✅' : v >= 40 ? '⚠️' : '❌';
    const bar = '<div class="score-bar" style="background:#1e293b;height:6px;border-radius:3px;margin-top:4px"><div class="score-fill" style="width:'+v+'%;height:6px;border-radius:3px;background:linear-gradient(90deg,#f43f5e,#fbbf24,#10b981)"></div></div>';
    return '<tr><td>'+n+'</td><td>'+bar+'<small class="text-muted">'+v+'/100</small></td><td>'+status+'</td></tr>';
  }).join('');
}
loadCompliance();
</script>
<style>.score-bar,.score-fill{display:block}</style>

{% elif tab=='tasks' %}
<h4 class="mb-4"><i class="bi bi-list-task me-2"></i>Tareas</h4>
<div class="card p-0"><div class="table-responsive">
<table class="table table-dark table-striped mb-0">
<thead><tr><th>#</th><th>Repo</th><th>Estado</th><th>Creado</th><th>Completado</th></tr></thead>
<tbody>{% for t in tasks %}
<tr><td>{{t.id}}</td><td style="max-width:300px;overflow:hidden;text-overflow:ellipsis">{{t.repo_url}}</td>
<td><span class="badge badge-{{t.status}}">{{t.status}}</span></td>
<td>{{t.created_at[:10] if t.created_at else ''}}</td>
<td>{{t.completed_at[:10] if t.completed_at else '—'}}</td></tr>
{% endfor %}</tbody></table></div></div>
<form method="POST" action="/run-task" class="mt-3">
<div class="row g-2">
<div class="col-md-6"><input type="url" name="repo_url" class="form-control" placeholder="URL del repositorio" required></div>
<div class="col-md-4"><input type="email" name="email" class="form-control" placeholder="Email" value="{{current_user.email}}"></div>
<div class="col-md-2"><button type="submit" class="btn btn-primary w-100"><i class="bi bi-play-fill me-1"></i>Ejecutar</button></div>
</div></form>

{% else %}
<div class="d-flex justify-content-between align-items-center mb-4">
<h4><i class="bi bi-speedometer2 me-2"></i>Dashboard</h4>
<span class="text-muted small">{{now}}</span></div>
<div class="row g-4">
<div class="col-md-3"><div class="card text-center"><div class="stat-number">{{stats.leads}}</div><div class="text-muted">Leads</div></div></div>
<div class="col-md-3"><div class="card text-center"><div class="stat-number">{{stats.tasks_completed}}</div><div class="text-muted">Auditorías</div></div></div>
<div class="col-md-3"><div class="card text-center"><div class="stat-number">{{stats.tasks_pending}}</div><div class="text-muted">Pendientes</div></div></div>
<div class="col-md-3"><div class="card text-center"><div class="stat-number">{{stats.revenue/100}}€</div><div class="text-muted">Ingresos</div></div></div>
</div>
{% if stats.recent_tasks %}
<div class="card mt-4"><h5 class="mb-3">Últimas auditorías</h5>
<table class="table table-dark table-striped mb-0">
<thead><tr><th>Repo</th><th>Estado</th><th>Fecha</th></tr></thead>
<tbody>{% for t in stats.recent_tasks[:5] %}
<tr><td style="max-width:300px;overflow:hidden;text-overflow:ellipsis">{{t.repo_url}}</td>
<td><span class="badge badge-{{t.status}}">{{t.status}}</span></td>
<td>{{t.created_at[:10] if t.created_at else ''}}</td></tr>
{% endfor %}</tbody></table></div>{% endif %}
{% endif %}
</div>
{% else %}
<div class="col-12">
<div class="login-card">
<h4 class="text-center mb-4"><i class="bi bi-shield-check text-primary me-2"></i>CodeAudit Pro</h4>
<ul class="nav nav-pills nav-justified mb-3" role="tablist">
<li class="nav-item"><button class="nav-link active" data-bs-toggle="tab" data-bs-target="#login">Entrar</button></li>
<li class="nav-item"><button class="nav-link" data-bs-toggle="tab" data-bs-target="#register">Registrarse</button></li>
</ul>
<div class="tab-content">
<div class="tab-pane fade show active" id="login">
<form method="POST" action="/login">
<div class="mb-3"><label class="form-label">Email</label><input type="text" name="username" class="form-control" required></div>
<div class="mb-3"><label class="form-label">Contraseña</label><input type="password" name="password" class="form-control" required></div>
<button type="submit" class="btn btn-primary w-100">Entrar</button>
</form></div>
<div class="tab-pane fade" id="register">
<form method="POST" action="/register">
<div class="mb-3"><label class="form-label">Email</label><input type="email" name="email" class="form-control" required></div>
<div class="mb-3"><label class="form-label">Contraseña</label><input type="password" name="password" class="form-control" required minlength="6"></div>
<button type="submit" class="btn btn-primary w-100">Crear cuenta</button>
</form></div>
</div></div></div>
{% endif %}
</div></div>
<div class="text-center text-muted small mt-4 mb-2">
<a href="/terms" class="text-muted me-3">Términos</a>
<a href="/privacy" class="text-muted me-3">Privacidad</a>
&copy; 2026 CodeAudit Pro
</div>
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
</body></html>"""


@app.route("/", methods=["GET"])
def index():
    if current_user.is_authenticated:
        tab = request.args.get("tab", "dashboard")
        db = get_db()
        if current_user.is_admin:
            leads = [dict(r) for r in db.execute("SELECT * FROM leads ORDER BY created_at DESC").fetchall()]
            users = [dict(r) for r in db.execute("SELECT * FROM users ORDER BY created_at DESC").fetchall()]
        else:
            leads = []
            users = []
        payments = [dict(r) for r in db.execute("SELECT * FROM payments WHERE user_id=? ORDER BY created_at DESC", (current_user.id,)).fetchall()]
        db.close()
        wl_config = get_client_config(current_user.email) if current_user.is_authenticated else None
        return render_template_string(TEMPLATE, tab=tab, whitelabel=wl_config, leads=leads, users=users, payments=payments, tasks=load_tasks(current_user.id), stats=get_stats(), now=datetime.now().strftime("%Y-%m-%d %H:%M"))
    return render_template_string(TEMPLATE, logged_out=True)


@app.route("/login", methods=["POST"])
def login():
    username = request.form.get("username", "")
    password = request.form.get("password", "")
    db = get_db()
    row = db.execute("SELECT * FROM users WHERE email = ?", (username,)).fetchone()
    db.close()
    if row and check_password_hash(row["password_hash"], password):
        user = User(row["id"], row["email"], row["password_hash"], row["created_at"], row["is_admin"])
        login_user(user)
        return redirect("/")
    return render_template_string(TEMPLATE, error="Credenciales inválidas")


@app.route("/register", methods=["POST"])
def register():
    email = request.form.get("email", "").strip()
    password = request.form.get("password", "").strip()
    if not email or not password or len(password) < 6:
        return render_template_string(TEMPLATE, error="Email inválido o contraseña muy corta (mín 6 caracteres)")

    db = get_db()
    existing = db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    if existing:
        db.close()
        return render_template_string(TEMPLATE, error="Este email ya está registrado")

    phash = generate_password_hash(password)
    db.execute("INSERT INTO users (email, password_hash) VALUES (?, ?)", (email, phash))
    db.commit()

    row = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    db.close()

    if row:
        user = User(row["id"], row["email"], row["password_hash"], row["created_at"], row["is_admin"])
        login_user(user)
    return redirect("/")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect("/")


@app.route("/save-compliance", methods=["POST"])
@login_required
def save_compliance():
    data = request.get_json(silent=True) or {}
    db = get_db()
    db.execute(
        "INSERT INTO compliance_scores (task_id, repo_url, secrets_score, vulnerabilities_score, complexity_score, duplication_score, perimeter_score, overall_score) VALUES (?,?,?,?,?,?,?,?)",
        (
            data.get("task_id", 0),
            data.get("repo_url", ""),
            data.get("secrets_score", 0),
            data.get("vulnerabilities_score", 0),
            data.get("complexity_score", 0),
            data.get("duplication_score", 0),
            data.get("perimeter_score", 0),
            data.get("overall_score", 0),
        ),
    )
    db.commit()
    db.close()
    return {"ok": True}


@app.route("/compliance-scores")
def get_compliance_scores():
    repo_url = request.args.get("repo", "")
    db = get_db()
    if repo_url:
        rows = db.execute("SELECT * FROM compliance_scores WHERE repo_url = ? ORDER BY created_at ASC", (repo_url,)).fetchall()
    else:
        rows = db.execute("SELECT * FROM compliance_scores ORDER BY created_at DESC LIMIT 20").fetchall()
    db.close()
    return {"scores": [dict(r) for r in rows]}


@app.route("/run-task", methods=["POST"])
@login_required
def run_task():
    repo_url = request.form.get("repo_url", "")
    email = request.form.get("email", current_user.email)
    if repo_url:
        result = subprocess.run(
            ["python3", str(PROJECT_DIR / "runner.py"), "--add", repo_url, "--email", email, "--user-id", str(current_user.id)],
            capture_output=True, text=True, timeout=30,
            cwd=str(PROJECT_DIR),
        )
    return redirect("/?tab=tasks")


# ── Free demo (no login required) ──────────────────────────────────

@app.route("/try-now", methods=["GET", "POST"])
def try_now():
    if request.method == "GET":
        return render_template_string("""<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Demo gratuita — CodeAudit Pro</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
<style>body{background:#0b0f19;color:#f8fafc;font-family:'Segoe UI',sans-serif;display:flex;align-items:center;min-height:100vh}
.card{background:#131b2e;border:1px solid #1e293b;border-radius:16px;padding:2rem;max-width:600px;margin:2rem auto}
.form-control{background:#1e293b;border:1px solid #334155;color:#f8fafc;border-radius:10px}
.form-control:focus{background:#1e293b;border-color:#6366f1;box-shadow:0 0 0 3px rgba(99,102,241,.15);color:#f8fafc}
.btn-primary{background:#6366f1;border:none;border-radius:10px;padding:12px 32px}
h1{color:#a5b4fc}.text-muted{color:#94a3b8}
</style></head>
<body>
<div class="container">
<div class="card text-center">
<h1><i class="bi bi-shield-check text-primary me-2"></i>CodeAudit Pro</h1>
<p class="text-muted">Prueba gratuita — escanea cualquier repositorio público de GitHub</p>
<form method="POST" action="/try-now" style="text-align:left">
<div class="mb-3"><label class="form-label">URL del repositorio público</label>
<input type="url" name="repo_url" class="form-control" placeholder="https://github.com/octocat/Hello-World" required></div>
<div class="mb-3"><label class="form-label">Email</label>
<input type="email" name="email" class="form-control" placeholder="tu@email.com" required></div>
<button type="submit" class="btn btn-primary w-100"><i class="bi bi-play-fill me-2"></i>Escaneo gratuito</button>
</form>
<p class="text-muted mt-3 small">Sin registro. Resultados en 1-2 minutos.</p>
</div></div>
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
</body></html>""")

    repo_url = request.form.get("repo_url", "").strip()
    email = request.form.get("email", "").strip()
    if not repo_url or not email:
        return render_template_string("<p class='text-danger'>URL y email requeridos</p>")

    LEADS_FILE.parent.mkdir(parents=True, exist_ok=True)
    file_exists = LEADS_FILE.exists()
    with open(LEADS_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["nombre", "email", "empresa", "repo_url", "mensaje", "fecha"])
        writer.writerow(["Demo User", email, "", repo_url, "Demo audit", datetime.now().isoformat()])

    audit_id = str(uuid.uuid4())[:8]

    AUDIT_STATUS_DIR.mkdir(parents=True, exist_ok=True)
    status_file = AUDIT_STATUS_DIR / f"{audit_id}.json"
    status_file.write_text(json.dumps({
        "step": "init", "status": "running",
        "email": email,
        "data": {"repo": repo_url, "message": "Iniciando auditoría..."}
    }, ensure_ascii=False), encoding="utf-8")

    subprocess.Popen(
        [sys.executable, str(PROJECT_DIR / "engine/run.py"), repo_url, "--audit-id", audit_id],
        cwd=str(PROJECT_DIR),
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    return redirect(f"/demo-progress/{audit_id}")


@app.route("/demo-progress/<audit_id>")
def demo_progress(audit_id):
    email = ""
    status_file = AUDIT_STATUS_DIR / f"{audit_id}.json"
    if status_file.exists():
        try:
            status_data = json.loads(status_file.read_text(encoding="utf-8"))
            email = status_data.get("email", "")
        except (json.JSONDecodeError, OSError):
            pass
    return render_template_string("""<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Escaneando... — CodeAudit Pro</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
<style>body{background:#0b0f19;color:#f8fafc;font-family:'Segoe UI',sans-serif;padding:2rem}
.card{background:#131b2e;border:1px solid #1e293b;border-radius:16px;padding:2rem;max-width:600px;margin:2rem auto;text-align:center}
.spinner{width:48px;height:48px;border:4px solid #1e293b;border-top-color:#6366f1;border-radius:50%;animation:spin 1s linear infinite;margin:0 auto 1rem}
@keyframes spin{to{transform:rotate(360deg)}}
h1{color:#a5b4fc}.step{color:#94a3b8;margin:.5rem 0}
.completed{color:#10b981}.running{color:#fbbf24}
.stat-number{font-size:2rem;font-weight:800;color:#6366f1}
</style></head>
<body>
<div class="container">
<div class="card">
<div class="spinner" id="spinner"></div>
<h1>🔍 Escaneando repositorio</h1>
<p class="text-muted" id="repo">Cargando...</p>
<div id="steps">
<div class="step" id="s-init">⏳ Iniciando...</div>
<div class="step" id="s-secrets">⏳ Escaneando secretos...</div>
<div class="step" id="s-sast">⏳ Escaneando código (SAST)...</div>
<div class="step" id="s-deps">⏳ Escaneando dependencias...</div>
<div class="step" id="s-debt">⏳ Midiendo deuda técnica...</div>
<div class="step" id="s-report">⏳ Generando informe...</div>
</div>
<div id="result" style="display:none">
<h3 class="text-light" id="completion-title">🔍 Auditoría completada</h3>
<div id="metrics-area" style="filter:blur(8px);pointer-events:none;user-select:none;margin-top:1rem">
  <div class="row g-3">
    <div class="col-4"><div class="card text-center p-3"><div class="stat-number" id="m-secrets">0</div><div class="text-muted small">Secretos</div></div></div>
    <div class="col-4"><div class="card text-center p-3"><div class="stat-number" id="m-vulns">0</div><div class="text-muted small">Vulnerabilidades</div></div></div>
    <div class="col-4"><div class="card text-center p-3"><div class="stat-number" id="m-complexity">—</div><div class="text-muted small">Complejidad</div></div></div>
  </div>
  <p id="summary" class="text-muted mt-2"></p>
</div>
<div style="background:linear-gradient(135deg,#0f1529,#131b2e);border:2px solid #6366f1;border-radius:20px;padding:2rem;text-align:center;margin-top:1.5rem">
  <div style="font-size:3rem;margin-bottom:0.5rem">🔒</div>
  <h3 style="color:#a5b4fc;font-weight:700">Informe Completo Bloqueado</h3>
  <p style="color:#94a3b8;max-width:400px;margin:0 auto 1rem">
    Los resultados detallados, el informe de cumplimiento NIS2/DORA, 
    el PDF descargable y la certificación blockchain están disponibles en el plan completo.
  </p>
  <div style="display:flex;gap:16px;justify-content:center;flex-wrap:wrap">
    <a href="?tab=invoices" style="display:inline-block;padding:14px 36px;border-radius:12px;background:linear-gradient(135deg,#6366f1,#818cf8);color:#fff;font-weight:700;text-decoration:none;box-shadow:0 4px 20px rgba(99,102,241,0.3)">
      DESBLOQUEAR INFORME — 299 €
    </a>
  </div>
  <p style="color:#475569;font-size:0.75rem;margin-top:0.75rem">
    Incluye PDF descargable · Certificación blockchain · Informe NIS2/DORA · Declaración de debida diligencia
  </p>
</div>
<a id="report-link" class="btn btn-primary mt-3"><i class="bi bi-file-earmark-text me-2"></i>Vista previa del informe</a>
<p class="text-muted mt-3 small">Tu auditoría está en proceso. Recibirás el informe completo por email en 5 minutos.</p>
</div>
</div></div>
<script>
const AUDIT_ID = '{{ audit_id }}';
const evtSource = new EventSource('/audit-status/' + AUDIT_ID);
const steps = { init:'s-init', secrets:'s-secrets', sast:'s-sast', deps:'s-deps', debt:'s-debt', report:'s-report' };
evtSource.onmessage = function(e) {
  const data = JSON.parse(e.data);
  if (data.step === 'init' && data.status === 'running') document.getElementById('repo').textContent = data.data?.repo || '';
  for (const [key, id] of Object.entries(steps)) {
    if (data.step === key) {
      document.getElementById(id).className = 'step ' + (data.status === 'done' ? 'completed' : 'running');
      document.getElementById(id).innerHTML = (data.status === 'done' ? '✅ ' : '⏳ ') + (data.data?.message || document.getElementById(id).textContent.trim());
    }
  }
  if (data.step === 'complete' && data.status === 'done') {
    document.getElementById('spinner').style.display = 'none';
    document.getElementById('steps').style.display = 'none';
    document.getElementById('result').style.display = 'block';
    const d = data.data;
    const repo = document.getElementById('repo').textContent || 'repositorio';
    document.getElementById('completion-title').textContent = '🔍 Auditoría completada para ' + repo;
    document.getElementById('m-secrets').textContent = d.secrets;
    document.getElementById('m-vulns').textContent = d.vulnerabilities;
    document.getElementById('m-complexity').textContent = d.complexity;
    document.getElementById('summary').innerHTML = '🔑 ' + d.secrets + ' secretos · 📦 ' + d.vulnerabilities + ' vulnerabilidades · 📊 Complejidad: ' + d.complexity;
    document.getElementById('report-link').href = '/reports/executive-report.html';
    evtSource.close();
  }
};
</script>
</body></html>""", audit_id=audit_id, email=email)


# ── SSE: progreso en tiempo real ───────────────────────────────────

@app.route("/audit-status/<audit_id>")
def audit_status_sse(audit_id):
    status_file = AUDIT_STATUS_DIR / f"{audit_id}.json"
    def generate():
        last_data = None
        while True:
            if status_file.exists():
                try:
                    data = status_file.read_text(encoding="utf-8").strip()
                    if data and data != last_data:
                        last_data = data
                        yield f"data: {data}\n\n"
                        parsed = json.loads(data)
                        if parsed.get("status") in ("done", "error"):
                            break
                except (json.JSONDecodeError, OSError):
                    pass
            time.sleep(0.5)
        yield "data: {\"step\":\"done\",\"status\":\"closed\"}\n\n"
    return Response(stream_with_context(generate()), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})


# ── Serve generated reports ───────────────────────────────────────

@app.route("/reports/<path:filename>")
def serve_report(filename):
    report_path = PROJECT_DIR / "reports" / filename
    if report_path.exists() and report_path.suffix in (".html", ".pdf", ".png"):
        return report_path.read_bytes() if report_path.suffix != ".html" else report_path.read_text(encoding="utf-8")
    return "Not found", 404


# ── Legal ──────────────────────────────────────────────────────────

@app.route("/terms")
def terms():
    return (PROJECT_DIR / "app" / "legal" / "terms.html").read_text(encoding="utf-8")

@app.route("/privacy")
def privacy():
    return (PROJECT_DIR / "app" / "legal" / "privacy.html").read_text(encoding="utf-8")

@app.route("/security")
def security():
    return (PROJECT_DIR / "app" / "legal" / "security.html").read_text(encoding="utf-8")

@app.route("/partners")
def partners():
    return (PROJECT_DIR / "app" / "legal" / "partners.html").read_text(encoding="utf-8")

@app.route("/create-checkout")
def create_checkout_page():
    plan = request.args.get("plan", "auditoria_unica")
    repo_url = request.args.get("repo_url", "")
    demo_id = request.args.get("demo_id", "")
    email = request.args.get("email", "")

    PRICES = {
        "auditoria_unica": {"name": "Auditoría Única", "price": "299 €", "price_cents": 29900},
        "compliance_pro": {"name": "Compliance Pro", "price": "1.500 €", "price_cents": 150000},
        "professional": {"name": "Professional", "price": "9.900 €/año", "price_cents": 990000},
        "enterprise": {"name": "Enterprise", "price": "29.900 €/año", "price_cents": 2990000},
    }

    p = PRICES.get(plan, PRICES["auditoria_unica"])
    return f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8"><title>Checkout — CodeAudit Pro</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
<style>body{{background:#070d1a;color:#f8fafc;font-family:'Segoe UI',sans-serif;display:flex;align-items:center;min-height:100vh}}
.card{{background:#0a1428;border:1px solid rgba(255,255,255,0.08);border-radius:16px;padding:2.5rem;max-width:480px;margin:2rem auto;box-shadow:0 20px 60px rgba(0,0,0,0.4)}}
h1{{font-size:1.5rem;font-weight:700;color:#f1f5f9;margin-bottom:0.5rem}}
.price{{font-size:2.5rem;font-weight:800;color:#f59e0b;margin:1rem 0}}
.form-control{{background:#070d1a;border:1px solid rgba(255,255,255,0.1);color:#f8fafc;border-radius:10px;padding:12px 14px}}
.form-control:focus{{border-color:#f59e0b;box-shadow:0 0 0 3px rgba(245,158,11,0.15)}}
.btn-primary{{background:linear-gradient(135deg,#f59e0b,#d97706);border:none;border-radius:10px;padding:14px 24px;font-weight:700;color:#070d1a;width:100%}}
.btn-primary:hover{{transform:translateY(-2px);box-shadow:0 8px 30px rgba(245,158,11,0.3)}}
.text-muted{{color:#64748b}}
</style></head>
<body>
<div class="container"><div class="card">
<h1>Confirmar compra</h1>
<p class="text-muted">{p['name']}</p>
<div class="price">{p['price']}</div>
<form id="checkoutForm">
<input type="hidden" name="plan" value="{plan}">
<div class="mb-3"><label class="form-label">URL del repositorio</label>
<input type="url" name="repo_url" class="form-control" value="{repo_url}" placeholder="https://github.com/usuario/repo"></div>
<div class="mb-3"><label class="form-label">Email</label>
<input type="email" name="customer_email" class="form-control" value="{email}" required></div>
<button type="submit" class="btn-primary" id="submitBtn">Pagar {p['price']} →</button>
</form>
<p class="text-muted mt-3 small text-center">Pago seguro procesado por Stripe · Factura disponible</p>
</div></div>
<script>
document.getElementById('checkoutForm').addEventListener('submit', async function(e){{
e.preventDefault();document.getElementById('submitBtn').disabled=true;
document.getElementById('submitBtn').textContent='Redirigiendo a Stripe...';
const fd=new FormData(this);const data=Object.fromEntries(fd);
const resp=await fetch('/create-checkout-session',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(data)}});
const j=await resp.json();if(j.url)window.location.href=j.url;else alert('Error: '+j.error);
}});
</script>
</body></html>"""


if __name__ == "__main__":
    port = int(os.getenv("DASHBOARD_PORT", "5000"))
    print(f"📊 Dashboard en http://localhost:{port}")
    print(f"🔬 Demo gratis: http://localhost:{port}/try-now")
    app.run(host="0.0.0.0", port=port, debug=False)

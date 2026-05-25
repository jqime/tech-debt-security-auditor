#!/usr/bin/env python3
import csv
import json
import os
import sqlite3
import subprocess
from datetime import datetime
from pathlib import Path

from flask import Flask, redirect, render_template_string, request, url_for
from flask_login import LoginManager, UserMixin, current_user, login_required, login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash
from app.whitelabel.whitelabel import whitelabel_bp, get_client_config

PROJECT_DIR = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_DIR / "data"
DB_PATH = DATA_DIR / "dashboard.db"
LEADS_FILE = DATA_DIR / "leads.csv"
TASKS_FILE = DATA_DIR / "tasks.json"

ADMIN_USER = os.getenv("DASHBOARD_USER", "admin")
ADMIN_PASS = os.getenv("DASHBOARD_PASS", "admin123")

app = Flask(__name__)
app.secret_key = os.getenv("DASHBOARD_SECRET", "cambiar-en-produccion-123456")
app.register_blueprint(whitelabel_bp)
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


def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            is_admin INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            repo_url TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT (datetime('now')),
            completed_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT,
            email TEXT,
            empresa TEXT,
            repo_url TEXT,
            mensaje TEXT,
            converted INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            stripe_session_id TEXT,
            amount INTEGER,
            currency TEXT DEFAULT 'eur',
            status TEXT DEFAULT 'completed',
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS compliance_scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER,
            repo_url TEXT,
            secrets_score REAL,
            vulnerabilities_score REAL,
            complexity_score REAL,
            duplication_score REAL,
            perimeter_score REAL,
            overall_score REAL,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (task_id) REFERENCES tasks(id)
        );
    """)
    # Create admin if not exists
    existing = conn.execute("SELECT id FROM users WHERE email = ?", (ADMIN_USER,)).fetchone()
    if not existing:
        conn.execute(
            "INSERT INTO users (email, password_hash, is_admin) VALUES (?, ?, 1)",
            (ADMIN_USER, generate_password_hash(ADMIN_PASS)),
        )
        conn.commit()
    conn.close()


init_db()


@login_manager.user_loader
def load_user(user_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    if row:
        return User(row["id"], row["email"], row["password_hash"], row["created_at"], row["is_admin"])
    return None


def load_tasks(user_id=None, limit=100):
    conn = get_db()
    if current_user.is_authenticated and current_user.is_admin:
        rows = conn.execute("SELECT * FROM tasks ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    elif user_id:
        rows = conn.execute("SELECT * FROM tasks WHERE user_id = ? ORDER BY created_at DESC LIMIT ?", (user_id, limit)).fetchall()
    else:
        rows = []
    conn.close()
    return [dict(r) for r in rows]


def load_leads():
    rows = []
    conn = get_db()
    try:
        rows = conn.execute("SELECT * FROM leads ORDER BY created_at DESC").fetchall()
    except Exception:
        pass
    conn.close()
    return [dict(r) for r in rows]


def get_stats():
    conn = get_db()
    total_users = conn.execute("SELECT COUNT(*) as c FROM users").fetchone()["c"]
    total_tasks = conn.execute("SELECT COUNT(*) as c FROM tasks").fetchone()["c"]
    completed = conn.execute("SELECT COUNT(*) as c FROM tasks WHERE status='completed'").fetchone()["c"]
    pending = conn.execute("SELECT COUNT(*) as c FROM tasks WHERE status='pending'").fetchone()["c"]
    total_leads = conn.execute("SELECT COUNT(*) as c FROM leads").fetchone()["c"]
    total_payments = conn.execute("SELECT COUNT(*) as c FROM payments").fetchone()["c"]
    revenue = conn.execute("SELECT COALESCE(SUM(amount),0) as s FROM payments WHERE status='completed'").fetchone()["s"]
    recent = conn.execute("SELECT * FROM tasks ORDER BY created_at DESC LIMIT 10").fetchall()
    conn.close()
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
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
</body></html>"""


@app.route("/", methods=["GET"])
def index():
    if current_user.is_authenticated:
        tab = request.args.get("tab", "dashboard")
        conn = get_db()
        if current_user.is_admin:
            leads = [dict(r) for r in conn.execute("SELECT * FROM leads ORDER BY created_at DESC").fetchall()]
            users = [dict(r) for r in conn.execute("SELECT * FROM users ORDER BY created_at DESC").fetchall()]
        else:
            leads = []
            users = []
        payments = [dict(r) for r in conn.execute("SELECT * FROM payments WHERE user_id=? ORDER BY created_at DESC", (current_user.id,)).fetchall()]
        conn.close()
        wl_config = get_client_config(current_user.email) if current_user.is_authenticated else None
        return render_template_string(TEMPLATE, tab=tab, whitelabel=wl_config, leads=leads, users=users, payments=payments, tasks=load_tasks(current_user.id), stats=get_stats(), now=datetime.now().strftime("%Y-%m-%d %H:%M"))
    return render_template_string(TEMPLATE, logged_out=True)


@app.route("/login", methods=["POST"])
def login():
    username = request.form.get("username", "")
    password = request.form.get("password", "")
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE email = ?", (username,)).fetchone()
    conn.close()
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

    conn = get_db()
    existing = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    if existing:
        conn.close()
        return render_template_string(TEMPLATE, error="Este email ya está registrado")

    phash = generate_password_hash(password)
    conn.execute("INSERT INTO users (email, password_hash) VALUES (?, ?)", (email, phash))
    conn.commit()

    row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()

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
    conn = get_db()
    conn.execute(
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
    conn.commit()
    conn.close()
    return {"ok": True}


@app.route("/compliance-scores")
def get_compliance_scores():
    repo_url = request.args.get("repo", "")
    conn = get_db()
    if repo_url:
        rows = conn.execute("SELECT * FROM compliance_scores WHERE repo_url = ? ORDER BY created_at ASC", (repo_url,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM compliance_scores ORDER BY created_at DESC LIMIT 20").fetchall()
    conn.close()
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


if __name__ == "__main__":
    port = int(os.getenv("DASHBOARD_PORT", "5000"))
    print(f"📊 Dashboard en http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)

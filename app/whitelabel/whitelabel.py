import base64
import json
import sqlite3
from datetime import datetime
from pathlib import Path

from flask import (
    Blueprint, jsonify, redirect, render_template_string, request,
)
from flask_login import current_user, login_required

PROJECT_DIR = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_DIR / "data"
DB_PATH = DATA_DIR / "dashboard.db"
LOGOS_DIR = DATA_DIR / "logos"

whitelabel_bp = Blueprint("whitelabel", __name__)


def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_whitelabel_db():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    LOGOS_DIR.mkdir(parents=True, exist_ok=True)
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS whitelabel_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id TEXT UNIQUE NOT NULL,
            subdomain TEXT UNIQUE NOT NULL,
            company_name TEXT NOT NULL,
            primary_color TEXT DEFAULT '#6366f1',
            logo_url TEXT DEFAULT '',
            custom_domain TEXT DEFAULT '',
            plan_type TEXT DEFAULT 'enterprise',
            features_json TEXT DEFAULT '{}',
            active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.commit()
    conn.close()


def get_subdomain():
    host = request.host.split(":")[0]
    parts = host.split(".")
    if len(parts) >= 3:
        return parts[0]
    return None


def get_client_config(email):
    if not email:
        return None
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM whitelabel_config WHERE client_id = ? AND active = 1",
        (email,),
    ).fetchone()
    conn.close()
    if row:
        return dict(row)
    return None


@whitelabel_bp.route("/whitelabel/<client_id>")
def get_whitelabel(client_id):
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM whitelabel_config WHERE client_id = ? AND active = 1",
        (client_id,),
    ).fetchone()
    conn.close()
    if not row:
        return jsonify({"error": "Config not found"}), 404
    config = dict(row)
    return jsonify({
        "primary_color": config["primary_color"],
        "logo_url": config["logo_url"],
        "company_name": config["company_name"],
        "subdomain": config["subdomain"],
        "plan_type": config["plan_type"],
    })


@whitelabel_bp.route("/whitelabel/save", methods=["POST"])
@login_required
def save_whitelabel():
    data = request.get_json(silent=True) or request.form.to_dict()
    client_id = data.get("client_id", current_user.email)
    subdomain = data.get("subdomain", get_subdomain() or client_id.split("@")[0])
    company_name = data.get("company_name", client_id)
    primary_color = data.get("primary_color", "#6366f1")
    logo_url = data.get("logo_url", "")
    custom_domain = data.get("custom_domain", "")
    plan_type = data.get("plan_type", "enterprise")
    features_json = data.get("features_json", "{}")
    active = int(data.get("active", 1))
    now = datetime.now().isoformat()

    conn = get_db()
    existing = conn.execute(
        "SELECT id FROM whitelabel_config WHERE client_id = ?", (client_id,)
    ).fetchone()

    if existing:
        conn.execute(
            """UPDATE whitelabel_config SET subdomain=?, company_name=?, primary_color=?,
               logo_url=?, custom_domain=?, plan_type=?, features_json=?, active=?, updated_at=?
               WHERE client_id=?""",
            (subdomain, company_name, primary_color, logo_url, custom_domain,
             plan_type, features_json, active, now, client_id),
        )
    else:
        conn.execute(
            """INSERT INTO whitelabel_config
               (client_id, subdomain, company_name, primary_color, logo_url,
                custom_domain, plan_type, features_json, active, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (client_id, subdomain, company_name, primary_color, logo_url,
             custom_domain, plan_type, features_json, active, now, now),
        )

    conn.commit()
    conn.close()
    return jsonify({"ok": True, "client_id": client_id})


@whitelabel_bp.route("/whitelabel/admin")
@login_required
def whitelabel_admin():
    if not current_user.is_admin:
        return redirect("/")
    conn = get_db()
    rows = conn.execute("SELECT * FROM whitelabel_config ORDER BY created_at DESC").fetchall()
    conn.close()
    clients = [dict(r) for r in rows]

    HTML = """<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Admin White Label - CodeAudit Pro</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
<link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.css" rel="stylesheet">
<style>
body{background:#0b0f19;color:#f8fafc;font-family:'Segoe UI',sans-serif}
.sidebar{background:#131b2e;min-height:100vh;border-right:1px solid #1e293b;padding:1.5rem}
.sidebar .nav-link{color:#94a3b8;padding:.75rem 1rem;border-radius:10px;margin-bottom:.25rem}
.sidebar .nav-link:hover,.sidebar .nav-link.active{background:#1e293b;color:#f8fafc}
.card{background:#131b2e;border:1px solid #1e293b;border-radius:16px;padding:1.5rem;margin-bottom:1rem}
.table{color:#f8fafc}.table th{border-color:#1e293b;color:#94a3b8}.table td{border-color:#1e293b}
</style></head>
<body>
<div class="container-fluid"><div class="row">
<div class="col-md-2 sidebar">
<h5 class="mb-4"><i class="bi bi-shield-check text-primary me-2"></i>CodeAudit</h5>
<nav class="nav flex-column">
<a class="nav-link" href="/"><i class="bi bi-speedometer2 me-2"></i>Dashboard</a>
<a class="nav-link active" href="/whitelabel/admin"><i class="bi bi-building me-2"></i>White Label</a>
<a class="nav-link" href="/logout"><i class="bi bi-box-arrow-left me-2"></i>Salir ({{current_user.email}})</a>
</nav></div>
<div class="col-md-10 p-4">
<h4 class="mb-4"><i class="bi bi-building me-2"></i>Clientes White Label</h4>
<div class="card p-0"><div class="table-responsive">
<table class="table table-dark table-striped mb-0">
<thead><tr><th>ID</th><th>Cliente</th><th>Subdominio</th><th>Empresa</th><th>Color</th><th>Plan</th><th>Activo</th><th>Creado</th></tr></thead>
<tbody>
{% for c in clients %}
<tr>
  <td>{{c.id}}</td>
  <td><code>{{c.client_id}}</code></td>
  <td><code>{{c.subdomain}}.codeauditpro.com</code></td>
  <td>{{c.company_name}}</td>
  <td><span style="display:inline-block;width:24px;height:24px;background:{{c.primary_color}};border-radius:4px;vertical-align:middle"></span> {{c.primary_color}}</td>
  <td>{{c.plan_type}}</td>
  <td>{{'✅' if c.active else '❌'}}</td>
  <td>{{c.created_at[:10]}}</td>
</tr>
{% endfor %}
</tbody></table></div></div>
</div></div></div>
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
</body></html>"""
    return render_template_string(HTML, clients=clients)


@whitelabel_bp.route("/my-company")
@login_required
def my_company():
    config = get_client_config(current_user.email)
    return render_template_string("""<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Mi Empresa - CodeAudit Pro</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
<link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.css" rel="stylesheet">
<style>
body{background:#0b0f19;color:#f8fafc;font-family:'Segoe UI',sans-serif}
.sidebar{background:#131b2e;min-height:100vh;border-right:1px solid #1e293b;padding:1.5rem}
.sidebar .nav-link{color:#94a3b8;padding:.75rem 1rem;border-radius:10px;margin-bottom:.25rem}
.sidebar .nav-link:hover,.sidebar .nav-link.active{background:#1e293b;color:#f8fafc}
.card{background:#131b2e;border:1px solid #1e293b;border-radius:16px;padding:1.5rem;margin-bottom:1rem}
.form-control{background:#1e293b;border:1px solid #334155;color:#f8fafc;border-radius:10px}
.form-control:focus{background:#1e293b;border-color:#6366f1;box-shadow:0 0 0 3px rgba(99,102,241,.15);color:#f8fafc}
.btn-primary{background:#6366f1;border:none;border-radius:10px}
.btn-primary:hover{background:#4f46e5}
</style></head>
<body>
<div class="container-fluid"><div class="row">
<div class="col-md-2 sidebar">
<h5 class="mb-4"><i class="bi bi-shield-check text-primary me-2"></i>CodeAudit</h5>
<nav class="nav flex-column">
<a class="nav-link" href="/"><i class="bi bi-speedometer2 me-2"></i>Dashboard</a>
<a class="nav-link active" href="/my-company"><i class="bi bi-building me-2"></i>Mi Empresa</a>
<a class="nav-link" href="/logout"><i class="bi bi-box-arrow-left me-2"></i>Salir ({{current_user.email}})</a>
</nav></div>
<div class="col-md-10 p-4">
<h4 class="mb-4"><i class="bi bi-building me-2"></i>Mi Empresa</h4>
<div class="row g-4">
<div class="col-md-6">
<div class="card"><h5>Personalización</h5>
<form method="POST" action="/whitelabel/save">
<div class="mb-3">
  <label class="form-label">Nombre de empresa</label>
  <input type="text" name="company_name" class="form-control" value="{{config.company_name if config else ''}}">
</div>
<div class="mb-3">
  <label class="form-label">Color primario (hex)</label>
  <input type="color" name="primary_color" class="form-control form-control-color" value="{{config.primary_color if config else '#6366f1'}}">
</div>
<div class="mb-3">
  <label class="form-label">Logo URL</label>
  <input type="url" name="logo_url" class="form-control" value="{{config.logo_url if config else ''}}" placeholder="https://tuempresa.com/logo.png">
</div>
<div class="mb-3">
  <label class="form-label">Subdominio</label>
  <input type="text" name="subdomain" class="form-control" value="{{config.subdomain if config else ''}}" placeholder="tudominio">
  <small class="text-muted">Ej: tudominio.codeauditpro.com</small>
</div>
<button type="submit" class="btn btn-primary"><i class="bi bi-save me-2"></i>Guardar</button>
</form>
</div></div>
<div class="col-md-6">
<div class="card"><h5>Vista previa</h5>
<div style="background:#0b0f19;padding:1rem;border-radius:8px;text-align:center">
  <div style="font-size:3rem;color:{{config.primary_color if config else '#6366f1'}}"><i class="bi bi-building"></i></div>
  <h4 style="color:{{config.primary_color if config else '#6366f1'}}">{{config.company_name if config else 'Mi Empresa'}}</h4>
  <p class="text-muted">Subdominio: <code>{{config.subdomain if config else 'tudominio'}}.codeauditpro.com</code></p>
  <p class="text-muted">{{'✅ Personalización activa' if config else '❌ Sin personalizar'}}</p>
</div></div></div>
</div>
<div class="card mt-4"><h5>Subir Logo (base64)</h5>
<form method="POST" action="/my-company/upload-logo" enctype="multipart/form-data">
<div class="mb-3">
  <label class="form-label">Seleccionar imagen PNG</label>
  <input type="file" name="logo" class="form-control" accept="image/png">
</div>
<button type="submit" class="btn btn-primary"><i class="bi bi-upload me-2"></i>Subir Logo</button>
</form>
{% if config and config.logo_url %}
<div class="mt-3"><img src="{{config.logo_url}}" alt="Logo" style="max-height:80px"></div>
{% endif %}
</div>
</div></div></div>
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
</body></html>""", config=config)


@whitelabel_bp.route("/my-company/upload-logo", methods=["POST"])
@login_required
def upload_logo():
    file = request.files.get("logo")
    if not file:
        return redirect("/my-company")
    LOGOS_DIR.mkdir(parents=True, exist_ok=True)
    logo_path = LOGOS_DIR / f"{current_user.email}.png"
    file.save(str(logo_path))
    with open(logo_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    data_uri = f"data:image/png;base64,{b64}"
    conn = get_db()
    existing = conn.execute(
        "SELECT id FROM whitelabel_config WHERE client_id = ?", (current_user.email,)
    ).fetchone()
    now = datetime.now().isoformat()
    if existing:
        conn.execute(
            "UPDATE whitelabel_config SET logo_url=?, updated_at=? WHERE client_id=?",
            (data_uri, now, current_user.email),
        )
    else:
        subdomain = get_subdomain() or current_user.email.split("@")[0]
        conn.execute(
            """INSERT INTO whitelabel_config
               (client_id, subdomain, company_name, logo_url, created_at, updated_at)
               VALUES (?,?,?,?,?,?)""",
            (current_user.email, subdomain, current_user.email, data_uri, now, now),
        )
    conn.commit()
    conn.close()
    return redirect("/my-company")


@whitelabel_bp.route("/my-company/config")
@login_required
def my_company_config():
    config = get_client_config(current_user.email)
    if not config:
        return jsonify({"error": "No config found"}), 404
    return jsonify({
        "primary_color": config["primary_color"],
        "logo_url": config["logo_url"],
        "company_name": config["company_name"],
        "subdomain": config["subdomain"],
    })


@whitelabel_bp.route("/my-company/save", methods=["POST"])
@login_required
def my_company_save():
    data = request.form.to_dict()
    client_id = current_user.email
    subdomain = data.get("subdomain", get_subdomain() or client_id.split("@")[0])
    company_name = data.get("company_name", client_id)
    primary_color = data.get("primary_color", "#6366f1")
    logo_url = data.get("logo_url", "")
    now = datetime.now().isoformat()
    conn = get_db()
    existing = conn.execute(
        "SELECT id FROM whitelabel_config WHERE client_id = ?", (client_id,)
    ).fetchone()
    if existing:
        conn.execute(
            """UPDATE whitelabel_config SET subdomain=?, company_name=?, primary_color=?,
               logo_url=?, updated_at=? WHERE client_id=?""",
            (subdomain, company_name, primary_color, logo_url, now, client_id),
        )
    else:
        conn.execute(
            """INSERT INTO whitelabel_config
               (client_id, subdomain, company_name, primary_color, logo_url, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?)""",
            (client_id, subdomain, company_name, primary_color, logo_url, now, now),
        )
    conn.commit()
    conn.close()
    return redirect("/?tab=mycompany")


init_whitelabel_db()

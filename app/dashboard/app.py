#!/usr/bin/env python3
import json
import os
import subprocess
from datetime import datetime
from pathlib import Path

from flask import Flask, redirect, render_template_string, request, send_file, url_for

PROJECT_DIR = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_DIR / "data"
LEADS_FILE = DATA_DIR / "leads.csv"
TASKS_FILE = DATA_DIR / "tasks.json"

ADMIN_USER = os.getenv("DASHBOARD_USER", "admin")
ADMIN_PASS = os.getenv("DASHBOARD_PASS", "admin123")

app = Flask(__name__)

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dashboard - CodeAudit Pro</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.css" rel="stylesheet">
    <style>
        body { background: #0b0f19; color: #f8fafc; font-family: 'Segoe UI', sans-serif; }
        .sidebar {
            background: #131b2e;
            min-height: 100vh;
            border-right: 1px solid #1e293b;
            padding: 1.5rem;
        }
        .sidebar .nav-link {
            color: #94a3b8;
            padding: 0.75rem 1rem;
            border-radius: 10px;
            margin-bottom: 0.25rem;
        }
        .sidebar .nav-link:hover, .sidebar .nav-link.active {
            background: #1e293b;
            color: #f8fafc;
        }
        .card {
            background: #131b2e;
            border: 1px solid #1e293b;
            border-radius: 16px;
            padding: 1.5rem;
        }
        .stat-number {
            font-size: 2rem;
            font-weight: 800;
            color: #6366f1;
        }
        .table { color: #f8fafc; }
        .table th { border-color: #1e293b; color: #94a3b8; }
        .table td { border-color: #1e293b; }
        .badge-pending { background: #fbbf24; color: #0b0f19; }
        .badge-completed { background: #10b981; }
        .badge-failed { background: #f43f5e; }
        .login-card {
            max-width: 400px; margin: 100px auto;
            background: #131b2e; border: 1px solid #1e293b;
            border-radius: 16px; padding: 2rem;
        }
        .form-control {
            background: #1e293b; border: 1px solid #334155;
            color: #f8fafc; border-radius: 10px;
        }
        .form-control:focus {
            background: #1e293b; border-color: #6366f1;
            box-shadow: 0 0 0 3px rgba(99,102,241,0.15); color: #f8fafc;
        }
        .btn-primary { background: #6366f1; border: none; border-radius: 10px; }
        .btn-primary:hover { background: #4f46e5; }
    </style>
</head>
<body>
    <div class="container-fluid">
        <div class="row">
            {% if logged_in %}
            <div class="col-md-2 sidebar">
                <h5 class="mb-4"><i class="bi bi-shield-check text-primary me-2"></i>CodeAudit Pro</h5>
                <nav class="nav flex-column">
                    <a class="nav-link active" href="/"><i class="bi bi-speedometer2 me-2"></i>Dashboard</a>
                    <a class="nav-link" href="/?tab=leads"><i class="bi bi-people me-2"></i>Leads</a>
                    <a class="nav-link" href="/?tab=tasks"><i class="bi bi-list-task me-2"></i>Tareas</a>
                    <a class="nav-link" href="/?tab=reports"><i class="bi bi-file-earmark-text me-2"></i>Informes</a>
                    <a class="nav-link" href="/logout"><i class="bi bi-box-arrow-left me-2"></i>Salir</a>
                </nav>
            </div>
            <div class="col-md-10 p-4">
                {% if tab == 'leads' %}
                    <h4 class="mb-4"><i class="bi bi-people me-2"></i>Leads / Prospectos</h4>
                    <div class="card p-0">
                        <div class="table-responsive">
                            <table class="table table-dark table-striped mb-0">
                                <thead><tr><th>#</th><th>Nombre</th><th>Web</th><th>Email</th><th>Teléfono</th><th>Ciudad</th></tr></thead>
                                <tbody>
                                {% for lead in leads %}
                                    <tr>
                                        <td>{{ loop.index }}</td>
                                        <td>{{ lead.name }}</td>
                                        <td><a href="https://{{ lead.web }}" target="_blank" class="text-primary">{{ lead.web }}</a></td>
                                        <td>{{ lead.email }}</td>
                                        <td>{{ lead.phone }}</td>
                                        <td>{{ lead.city }}</td>
                                    </tr>
                                {% endfor %}
                                </tbody>
                            </table>
                        </div>
                    </div>
                {% elif tab == 'tasks' %}
                    <h4 class="mb-4"><i class="bi bi-list-task me-2"></i>Tareas de Auditoría</h4>
                    <div class="card p-0">
                        <div class="table-responsive">
                            <table class="table table-dark table-striped mb-0">
                                <thead><tr><th>#</th><th>Repo</th><th>Cliente</th><th>Plan</th><th>Estado</th><th>Creado</th></tr></thead>
                                <tbody>
                                {% for t in tasks %}
                                    <tr>
                                        <td>{{ t.id }}</td>
                                        <td style="max-width: 250px; overflow: hidden; text-overflow: ellipsis;">{{ t.repo_url }}</td>
                                        <td>{{ t.customer_email }}</td>
                                        <td>{{ t.plan_type }}</td>
                                        <td><span class="badge badge-{{ t.status }}">{{ t.status }}</span></td>
                                        <td>{{ t.created_at[:10] }}</td>
                                    </tr>
                                {% endfor %}
                                </tbody>
                            </table>
                        </div>
                    </div>
                    <form method="POST" action="/run-task" class="mt-3">
                        <div class="row g-2">
                            <div class="col-md-6">
                                <input type="url" name="repo_url" class="form-control" placeholder="URL del repositorio" required>
                            </div>
                            <div class="col-md-4">
                                <input type="email" name="email" class="form-control" placeholder="Email del cliente" required>
                            </div>
                            <div class="col-md-2">
                                <button type="submit" class="btn btn-primary w-100">
                                    <i class="bi bi-play-fill me-1"></i>Ejecutar
                                </button>
                            </div>
                        </div>
                    </form>
                {% elif tab == 'reports' %}
                    <h4 class="mb-4"><i class="bi bi-file-earmark-text me-2"></i>Informes Generados</h4>
                    <div class="card">
                        {% if reports %}
                        <ul class="list-group list-group-flush bg-transparent">
                            {% for r in reports %}
                            <li class="list-group-item bg-transparent text-light d-flex justify-content-between align-items-center">
                                <span><i class="bi bi-filetype-html text-primary me-2"></i>{{ r.name }}</span>
                                <span class="text-muted small">{{ r.modified }}</span>
                            </li>
                            {% endfor %}
                        </ul>
                        {% else %}
                        <p class="text-muted mb-0">No hay informes generados aún.</p>
                        {% endif %}
                    </div>
                {% else %}
                    <div class="d-flex justify-content-between align-items-center mb-4">
                        <h4><i class="bi bi-speedometer2 me-2"></i>Dashboard</h4>
                        <span class="text-muted small">{{ now }}</span>
                    </div>
                    <div class="row g-4">
                        <div class="col-md-3">
                            <div class="card text-center">
                                <div class="stat-number">{{ stats.leads }}</div>
                                <div class="text-muted">Leads generados</div>
                            </div>
                        </div>
                        <div class="col-md-3">
                            <div class="card text-center">
                                <div class="stat-number">{{ stats.tasks_completed }}</div>
                                <div class="text-muted">Auditorías completadas</div>
                            </div>
                        </div>
                        <div class="col-md-3">
                            <div class="card text-center">
                                <div class="stat-number">{{ stats.tasks_pending }}</div>
                                <div class="text-muted">Pendientes</div>
                            </div>
                        </div>
                        <div class="col-md-3">
                            <div class="card text-center">
                                <div class="stat-number">{{ stats.revenue }}€</div>
                                <div class="text-muted">Ingresos estimados</div>
                            </div>
                        </div>
                    </div>
                    {% if stats.recent_tasks %}
                    <div class="card mt-4">
                        <h5 class="mb-3">Últimas auditorías</h5>
                        <div class="table-responsive">
                            <table class="table table-dark table-striped mb-0">
                                <thead><tr><th>Repo</th><th>Cliente</th><th>Estado</th><th>Fecha</th></tr></thead>
                                <tbody>
                                {% for t in stats.recent_tasks[:5] %}
                                    <tr>
                                        <td style="max-width: 250px; overflow: hidden; text-overflow: ellipsis;">{{ t.repo_url }}</td>
                                        <td>{{ t.customer_email }}</td>
                                        <td><span class="badge badge-{{ t.status }}">{{ t.status }}</span></td>
                                        <td>{{ t.created_at[:10] }}</td>
                                    </tr>
                                {% endfor %}
                                </tbody>
                            </table>
                        </div>
                    </div>
                    {% endif %}
                {% endif %}
            </div>
            {% else %}
            <div class="col-12">
                <div class="login-card">
                    <h4 class="text-center mb-4"><i class="bi bi-shield-check text-primary me-2"></i>CodeAudit Pro</h4>
                    <form method="POST">
                        <div class="mb-3">
                            <label class="form-label">Usuario</label>
                            <input type="text" name="username" class="form-control" required>
                        </div>
                        <div class="mb-3">
                            <label class="form-label">Contraseña</label>
                            <input type="password" name="password" class="form-control" required>
                        </div>
                        <button type="submit" class="btn btn-primary w-100">Entrar</button>
                    </form>
                </div>
            </div>
            {% endif %}
        </div>
    </div>
</body>
</html>"""


def load_leads() -> list[dict]:
    if not LEADS_FILE.exists():
        return []
    import csv
    with open(LEADS_FILE, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_tasks() -> list[dict]:
    if not TASKS_FILE.exists():
        return []
    try:
        return json.loads(TASKS_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []


def load_reports() -> list[dict]:
    reports_dir = PROJECT_DIR / "reports"
    if not reports_dir.exists():
        return []
    reports = []
    for f in sorted(reports_dir.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
        if f.suffix in (".html", ".json"):
            reports.append({"name": f.name, "modified": datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M")})
    return reports


def get_stats() -> dict:
    tasks = load_tasks()
    completed = [t for t in tasks if t["status"] == "completed"]
    pending = [t for t in tasks if t["status"] == "pending"]
    revenue = len(completed) * 299
    return {
        "leads": len(load_leads()),
        "tasks_completed": len(completed),
        "tasks_pending": len(pending),
        "revenue": revenue,
        "recent_tasks": tasks[-10:],
    }


@app.route("/", methods=["GET", "POST"])
def index():
    logged_in = request.cookies.get("session") == "authenticated"

    if request.method == "POST" and not logged_in:
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        if username == ADMIN_USER and password == ADMIN_PASS:
            resp = redirect("/")
            resp.set_cookie("session", "authenticated")
            return resp
        return render_template_string(HTML_TEMPLATE, logged_in=False, error="Credenciales inválidas")

    tab = request.args.get("tab", "dashboard")
    return render_template_string(
        HTML_TEMPLATE,
        logged_in=logged_in,
        tab=tab,
        leads=load_leads(),
        tasks=load_tasks(),
        reports=load_reports(),
        stats=get_stats(),
        now=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )


@app.route("/logout")
def logout():
    resp = redirect("/")
    resp.delete_cookie("session")
    return resp


@app.route("/run-task", methods=["POST"])
def run_task():
    repo_url = request.form.get("repo_url", "")
    email = request.form.get("email", "cliente@ejemplo.com")
    if repo_url:
        subprocess.Popen(
            ["python3", str(PROJECT_DIR / "runner.py"), "--add", repo_url, "--email", email],
            cwd=str(PROJECT_DIR),
        )
    return redirect("/?tab=tasks")


if __name__ == "__main__":
    port = int(os.getenv("DASHBOARD_PORT", "5000"))
    print(f"Dashboard: http://localhost:{port}  (user: {ADMIN_USER})")
    app.run(host="0.0.0.0", port=port, debug=False)

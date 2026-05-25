#!/usr/bin/env python3
import json
import os
import re
from datetime import datetime

def extract_and_load_json(file_path):
    """
    Attempts to read a file, clean any LLM markdown/conversational wrapper,
    and parse the JSON content robustly.
    """
    if not os.path.exists(file_path):
        return {}
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read().strip()
        
        if not content:
            return {}
        
        # Regex to find JSON blocks ```json ... ``` or just ``` ... ```
        code_block_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
        if code_block_match:
            content = code_block_match.group(1)
        else:
            # Try to find the first '{' and last '}'
            brace_match = re.search(r'(\{.*\})', content, re.DOTALL)
            if brace_match:
                content = brace_match.group(1)
        
        return json.loads(content)
    except Exception as e:
        print(f"Warning parsing {file_path}: {e}. Trying raw fallback...")
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}

def main():
    # Load reports
    security = extract_and_load_json('reports/security-report.json')
    debt = extract_and_load_json('reports/debt-report.json')

    # Extract metrics
    secrets = security.get('secrets', [])
    vulnerabilities = security.get('vulnerable_dependencies', [])
    average_complexity = debt.get('average_complexity', 'N/A')
    duplicated_lines = debt.get('duplicated_lines', 0)

    # Count helpers
    num_secrets = len(secrets)
    num_vulns = len(vulnerabilities)
    
    # Format complexity display
    try:
        comp_val = float(average_complexity)
        comp_display = f"{comp_val:.2f}"
        if comp_val < 5:
            comp_status = "Good (Low Complexity)"
            comp_color = "#10b981" # Green
        elif comp_val < 15:
            comp_status = "Moderate"
            comp_color = "#f59e0b" # Amber
        else:
            comp_status = "High Complexity"
            comp_color = "#ef4444" # Red
    except Exception:
        comp_display = str(average_complexity)
        comp_status = "Under Evaluation"
        comp_color = "#94a3b8"

    # Define color variables
    color_accent_red = "var(--accent-red)"
    color_accent_green = "var(--accent-green)"
    color_accent_amber = "var(--accent-amber)"

    color_secrets = color_accent_red if num_secrets > 0 else color_accent_green
    color_vulns = color_accent_amber if num_vulns > 0 else color_accent_green
    color_duplicates = color_accent_amber if duplicated_lines > 0 else color_accent_green
    color_dupl_text = comp_color if duplicated_lines > 50 else color_accent_green

    # Pre-render list elements to avoid nested f-strings (for compatibility with Python < 3.12)
    secrets_html = ""
    for s in secrets:
        line = s.get('line', 'N/A')
        file_path = s.get('file', 'N/A')
        reason = s.get('reason', 'Clave/Token detectado en el archivo.')
        secrets_html += f"""
        <li class="issue-item">
            <div class="issue-meta">
                <span>🔑 SECRETO EXPUESTO</span>
                <span>Línea {line}</span>
            </div>
            <div class="issue-path">{file_path}</div>
            <div class="issue-desc">{reason}</div>
        </li>
        """

    vulns_html = ""
    for v in vulnerabilities:
        severity = v.get('severity', 'HIGH')
        name = v.get('name', 'N/A')
        version = v.get('version', 'N/A')
        vulns_html += f"""
        <li class="issue-item">
            <div class="issue-meta">
                <span>📦 VULNERABILIDAD</span>
                <span class="badge badge-red">{severity}</span>
            </div>
            <div class="issue-path">{name} @ {version}</div>
            <div class="issue-desc">Dependencia externa insegura detectada en el escaneo de paquetes.</div>
        </li>
        """

    empty_state_html = ""
    if num_secrets == 0 and num_vulns == 0:
        empty_state_html = """
        <div class="empty-state">
            <div class="empty-icon">✓</div>
            <p>No se encontraron secretos expuestos ni dependencias con vulnerabilidades conocidas.</p>
        </div>
        """

    security_badge_class = "badge-red" if (num_secrets > 0 or num_vulns > 0) else "badge-green"
    security_badge_text = "Riesgo Detectado" if (num_secrets > 0 or num_vulns > 0) else "Seguro"

    # HTML Output
    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Informe Ejecutivo DevSecOps | Auditoría de Código</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-base: #0b0f19;
            --bg-surface: #131b2e;
            --bg-card: #1e293b;
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
            --primary: #6366f1;
            --primary-light: #818cf8;
            --accent-green: #10b981;
            --accent-red: #f43f5e;
            --accent-amber: #fbbf24;
            --border: #334155;
        }}

        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}

        body {{
            background-color: var(--bg-base);
            color: var(--text-main);
            font-family: 'Inter', sans-serif;
            line-height: 1.6;
            padding: 2rem 1.5rem;
        }}

        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}

        header {{
            background: linear-gradient(135deg, #1e1b4b 0%, #1e293b 100%);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 2.5rem;
            margin-bottom: 2rem;
            position: relative;
            overflow: hidden;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.25);
        }}

        header::before {{
            content: '';
            position: absolute;
            top: -50%;
            right: -20%;
            width: 300px;
            height: 300px;
            background: radial-gradient(circle, rgba(99, 102, 241, 0.2) 0%, transparent 70%);
            pointer-events: none;
        }}

        h1 {{
            font-size: 2.25rem;
            font-weight: 700;
            letter-spacing: -0.025em;
            background: linear-gradient(to right, #a5b4fc, #818cf8);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 0.5rem;
        }}

        .timestamp {{
            color: var(--text-muted);
            font-size: 0.875rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}

        /* Metrics grid */
        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
            gap: 1.5rem;
            margin-bottom: 2rem;
        }}

        .metric-card {{
            background-color: var(--bg-surface);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 1.75rem;
            transition: all 0.3s ease;
            position: relative;
            overflow: hidden;
        }}

        .metric-card:hover {{
            transform: translateY(-4px);
            border-color: var(--primary-light);
            box-shadow: 0 8px 24px rgba(99, 102, 241, 0.15);
        }}

        .metric-card h3 {{
            color: var(--text-muted);
            font-size: 0.875rem;
            font-weight: 500;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 0.75rem;
        }}

        .metric-value {{
            font-size: 2.5rem;
            font-weight: 700;
            line-height: 1;
            margin-bottom: 0.5rem;
        }}

        .metric-label {{
            font-size: 0.875rem;
            color: var(--text-muted);
        }}

        /* Glow effects for cards */
        .card-security-critical {{
            border-left: 4px solid var(--accent-red);
        }}
        .card-security-warning {{
            border-left: 4px solid var(--accent-amber);
        }}
        .card-debt {{
            border-left: 4px solid var(--primary);
        }}

        /* Detailed sections */
        .section-wrapper {{
            display: grid;
            grid-template-columns: 1fr;
            gap: 2rem;
        }}

        @media (min-width: 900px) {{
            .section-wrapper {{
                grid-template-columns: 1fr 1fr;
            }}
        }}

        .details-panel {{
            background-color: var(--bg-surface);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 2rem;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
        }}

        .panel-title {{
            font-size: 1.5rem;
            font-weight: 600;
            margin-bottom: 1.5rem;
            padding-bottom: 0.5rem;
            border-bottom: 1px solid var(--border);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}

        .badge {{
            padding: 0.25rem 0.75rem;
            border-radius: 9999px;
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
        }}

        .badge-red {{
            background-color: rgba(244, 63, 94, 0.15);
            color: var(--accent-red);
        }}

        .badge-green {{
            background-color: rgba(16, 185, 129, 0.15);
            color: var(--accent-green);
        }}

        .badge-purple {{
            background-color: rgba(99, 102, 241, 0.15);
            color: var(--primary-light);
        }}

        .issue-list {{
            list-style: none;
            display: flex;
            flex-direction: column;
            gap: 1rem;
        }}

        .issue-item {{
            background-color: rgba(30, 41, 59, 0.5);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 1rem;
            display: flex;
            flex-direction: column;
            gap: 0.25rem;
        }}

        .issue-item:hover {{
            background-color: rgba(30, 41, 59, 0.8);
            border-color: #475569;
        }}

        .issue-meta {{
            display: flex;
            justify-content: space-between;
            font-size: 0.75rem;
            color: var(--text-muted);
        }}

        .issue-path {{
            font-family: monospace;
            color: #38bdf8;
            font-weight: 500;
            word-break: break-all;
        }}

        .issue-desc {{
            font-size: 0.9rem;
            color: var(--text-main);
        }}

        .empty-state {{
            text-align: center;
            padding: 3rem 1rem;
            color: var(--text-muted);
        }}

        .empty-icon {{
            font-size: 3rem;
            margin-bottom: 1rem;
            color: var(--accent-green);
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>Reporte Ejecutivo de Auditoría</h1>
            <div class="timestamp">
                <svg width="16" height="16" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-12a1 1 0 10-2 0v4a1 1 0 00.293.707l2.828 2.829a1 1 0 101.415-1.415L11 9.586V6z" clip-rule="evenodd"></path></svg>
                Generado el {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} (Hora Local)
            </div>
        </header>

        <!-- Metric cards summary -->
        <div class="metrics-grid">
            <div class="metric-card card-security-critical">
                <h3>Secretos Expuestos</h3>
                <div class="metric-value" style="color: {color_secrets}">
                    {num_secrets}
                </div>
                <div class="metric-label">API keys, contraseñas o tokens en código</div>
            </div>

            <div class="metric-card card-security-warning">
                <h3>Vulnerabilidades</h3>
                <div class="metric-value" style="color: {color_vulns}">
                    {num_vulns}
                </div>
                <div class="metric-label">Dependencias externas comprometidas</div>
            </div>

            <div class="metric-card card-debt">
                <h3>Complejidad Media</h3>
                <div class="metric-value" style="color: {comp_color}">
                    {comp_display}
                </div>
                <div class="metric-label">{comp_status}</div>
            </div>

            <div class="metric-card card-debt">
                <h3>Líneas Duplicadas</h3>
                <div class="metric-value" style="color: {color_duplicates}">
                    {duplicated_lines}
                </div>
                <div class="metric-label">Código copiado / redundante</div>
            </div>
        </div>

        <!-- Detailed Panel View -->
        <div class="section-wrapper">
            <!-- Security Panel -->
            <div class="details-panel">
                <div class="panel-title">
                    <span>🛡️ Seguridad y Secretos</span>
                    <span class="badge {security_badge_class}">
                        {security_badge_text}
                    </span>
                </div>

                <ul class="issue-list">
                    {secrets_html}
                    {vulns_html}
                    {empty_state_html}
                </ul>
            </div>

            <!-- Quality & Technical Debt Panel -->
            <div class="details-panel">
                <div class="panel-title">
                    <span>📊 Calidad y Deuda Técnica</span>
                    <span class="badge badge-purple">Métricas de Código</span>
                </div>

                <div style="display: flex; flex-direction: column; gap: 1.5rem;">
                    <div class="issue-item">
                        <h4 style="font-size: 1rem; margin-bottom: 0.5rem; color: #a5b4fc;">Complejidad Ciclomática</h4>
                        <p style="font-size: 0.9rem; color: var(--text-muted);">
                            La complejidad mide la cantidad de caminos independientes a través del código. Una complejidad promedio menor a 5 es excelente y facilita el mantenimiento.
                        </p>
                        <div style="margin-top: 0.75rem; font-size: 1.25rem; font-weight: 600; color: {comp_color};">
                            {comp_display} &mdash; <span style="font-size: 1rem; font-weight: 400; color: var(--text-muted);">{comp_status}</span>
                        </div>
                    </div>

                    <div class="issue-item">
                        <h4 style="font-size: 1rem; margin-bottom: 0.5rem; color: #a5b4fc;">Duplicidad de Código</h4>
                        <p style="font-size: 0.9rem; color: var(--text-muted);">
                            Líneas de código duplicadas aumentan el esfuerzo de mantenimiento y el riesgo de inconsistencias al corregir errores.
                        </p>
                        <div style="margin-top: 0.75rem; font-size: 1.25rem; font-weight: 600; color: {color_dupl_text};">
                            {duplicated_lines} <span style="font-size: 1rem; font-weight: 400; color: var(--text-muted);">líneas redundantes detectadas</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</body>
</html>
"""

    # Make sure output directory exists
    os.makedirs('reports', exist_ok=True)
    with open('reports/executive-report.html', 'w', encoding='utf-8') as f:
        f.write(html)
    print("Reporte visual ejecutivo generado: reports/executive-report.html")

if __name__ == '__main__':
    main()

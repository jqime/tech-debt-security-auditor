#!/bin/bash
# Enterprise Migration & Demo Tool - CodeAudit Pro
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR/.."

MODE="${1:-demo}"  # demo|sandbox|full

echo "=========================================="
echo "🏢 CodeAudit Pro — Enterprise Migration"
echo "=========================================="

case "$MODE" in
  demo)
    echo ""
    echo "📦 [1/4] Creando cliente de demostración..."
    # Generate demo client data with fictional enterprise
    CLIENT_ID="demo-enterprise-$(date +%s)"
    COMPANY="FinTech Payments S.L."
    EMAIL="cto@fintech-payments.com"
    REPO="https://github.com/fintech-payments/core-platform"
    
    echo "   Cliente: $COMPANY"
    echo "   Email:   $EMAIL"
    echo "   Repo:    $REPO"
    
    # Insert into SQLite if dashboard.db exists
    DB="$PROJECT_DIR/data/dashboard.db"
    if [ -f "$DB" ]; then
        python3 -c "
import sqlite3, json
conn = sqlite3.connect('$DB')
c = conn.cursor()
c.execute('INSERT OR IGNORE INTO whitelabel_config (client_id, subdomain, company_name, primary_color, logo_url, plan_type, features_json) VALUES (?,?,?,?,?,?,?)',
    ('$CLIENT_ID', 'fintech-payments', '$COMPANY', '#059669', '', 'enterprise', json.dumps({
        'siem_enabled': True,
        'auto_remediate': True,
        'continuous_audit': True,
        'white_label': True,
        'max_repos': 50,
        'support_tier': '24/7'
    })))
conn.commit()
conn.close()
print('   ✅ Cliente insertado en whitelabel_config')
" 2>&1 || echo "   ⚠️ whitelabel_config table may not exist yet"
    fi
    
    echo ""
    echo "📊 [2/4] Generando datos históricos de compliance..."
    # Generate 12 weeks of fake compliance scores for evolution chart
    python3 -c "
import sqlite3, json, random, datetime
random.seed(42)
DB = '$PROJECT_DIR/data/dashboard.db'
conn = sqlite3.connect(DB)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS compliance_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id TEXT, repo_url TEXT, score REAL,
    critical_count INTEGER, high_count INTEGER,
    mttr_hours REAL, created_at TEXT
)''')
base = 45
for w in range(12):
    date = (datetime.datetime.now() - datetime.timedelta(weeks=11-w)).isoformat()
    score = min(95, base + w * 3 + random.randint(-5, 8))
    crit = max(0, 8 - w // 2 + random.randint(-1, 2))
    high = max(1, 12 - w // 3 + random.randint(-2, 3))
    mttr = max(4, 72 - w * 4 + random.randint(-8, 8))
    c.execute('INSERT INTO compliance_history (client_id, repo_url, score, critical_count, high_count, mttr_hours, created_at) VALUES (?,?,?,?,?,?,?)',
        ('$CLIENT_ID', '$REPO', score, crit, high, mttr, date))
conn.commit()
conn.close()
print('   ✅ 12 semanas de datos históricos generados')
"

    echo ""
    echo "🚀 [3/4] Ejecutando auditoría demo..."
    cd "$PROJECT_DIR" && python3 engine/run.py . 2>&1 | tail -5
    
    echo ""
    echo "📋 [4/4] Generando compliance + certificación..."
    cd "$PROJECT_DIR" && python3 compliance_report.py 2>&1 | tail -3
    python3 certify.py --certify 2>&1 | tail -3
    
    echo ""
    echo "=========================================="
    echo "✅ Demo Enterprise lista"
    echo "=========================================="
    echo ""
    echo "   Cliente:     $COMPANY"
    echo "   Client ID:   $CLIENT_ID"
    echo "   Subdominio:  fintech-payments.codeauditpro.com"
    echo "   Repos:       $REPO"
    echo ""
    echo "   Abre el dashboard y selecciona 'Cumplimiento Continuo'"
    echo "   para ver la evolución temporal del score."
    echo ""
    ;;
    
  sandbox)
    echo ""
    echo "🧪 [MODO SANDBOX] Activando remediación simulada..."
    echo ""
    echo "   En este modo, auto_remediate.py mostrará los comandos"
    echo "   que ejecutaría sin hacer cambios reales."
    echo ""
    echo "   Ejemplo de uso:"
    echo "   python3 auto_remediate.py --repo https://github.com/octocat/Hello-World --dry-run"
    echo ""
    # Run auto-remediate in dry-run mode on the project's security report
    if [ -f "$PROJECT_DIR/reports/security-report.json" ]; then
        cd "$PROJECT_DIR" && python3 auto_remediate.py --repo https://github.com/octocat/Hello-World --dry-run 2>&1
    else
        echo "   ⚠️ No se encuentra reports/security-report.json."
        echo "   Ejecuta primero: ./run_audit.sh https://github.com/octocat/Hello-World"
    fi
    echo ""
    echo "=========================================="
    echo "✅ Sandbox mode completado"
    echo "=========================================="
    echo ""
    echo "   Para salir del sandbox y ejecutar remediación real:"
    echo "   export GITHUB_TOKEN=ghp_xxx"
    echo "   python3 auto_remediate.py --repo <url>"
    echo ""
    ;;
    
  full)
    echo ""
    echo "🏗️ [MODO FULL] Migración enterprise completa..."
    echo ""
    bash "$0" demo
    echo ""
    bash "$0" sandbox
    echo ""
    echo "   Ahora puedes iniciar los servicios:"
    echo "   python3 app/dashboard/app.py &"
    echo "   python3 continuous_audit.py --daemon &"
    echo "   python3 integrations/siem.py &"
    echo ""
    ;;
    
  *)
    echo "Uso: $0 [demo|sandbox|full]"
    echo ""
    echo "  demo    - Crea cliente demo con datos históricos (default)"
    echo "  sandbox - Modo seguro para probar remediación"
    echo "  full    - Ejecuta demo + sandbox + muestra servicios"
    ;;
esac

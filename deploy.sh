#!/bin/bash
set -e

echo "=========================================="
echo "🚀 CodeAudit Pro - Despliegue en VPS"
echo "=========================================="
echo ""

# 1. Detectar SO e instalar dependencias del sistema
echo "📦 Instalando dependencias del sistema..."
if command -v apt-get &>/dev/null; then
    sudo apt-get update -qq
    sudo apt-get install -y -qq python3 python3-pip git nodejs npm curl
elif command -v yum &>/dev/null; then
    sudo yum install -y python3 python3-pip git nodejs npm curl
else
    echo "⚠️  No se pudo instalar dependencias. Hazlo manualmente."
fi

# 2. Instalar opencode CLI
echo ""
echo "🤖 Instalando OpenCode CLI..."
if ! command -v opencode &>/dev/null; then
    npm install -g opencode-ai
    echo "✓ opencode instalado"
else
    echo "✓ opencode ya instalado"
fi

# 3. Instalar dependencias Python
echo ""
echo "🐍 Instalando dependencias Python..."
pip install flask flask-login flask-cors werkzeug stripe 2>&1 | tail -1

# 4. Verificar variables de entorno
echo ""
echo "🔐 Verificando variables de entorno..."
check_var() {
    if [ -z "${!1}" ]; then
        echo "   ⚠️  $1 no definida. El servicio usará modo simulado."
    else
        echo "   ✅ $1 configurada"
    fi
}
check_var "STRIPE_SECRET_KEY"
check_var "EMAIL_USER"
check_var "EMAIL_PASS"
check_var "DASHBOARD_USER"
check_var "DASHBOARD_PASS"

# 5. Crear estructura de datos
echo ""
echo "📁 Creando directorios de datos..."
mkdir -p data reports

# 6. Matar procesos previos
echo ""
echo "🔄 Limpiando procesos previos..."
pkill -f "landing_handler.py" 2>/dev/null || true
pkill -f "payment.py" 2>/dev/null || true
pkill -f "dashboard/app.py" 2>/dev/null || true
pkill -f "runner.py" 2>/dev/null || true
sleep 1

# 7. Arrancar servicios
echo ""
echo "🚀 Arrancando servicios..."
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

nohup python3 landing_handler.py > /tmp/landing_handler.log 2>&1 &
echo "   ✅ Landing handler (puerto 5001) PID=$!"

nohup python3 payment.py > /tmp/payment.log 2>&1 &
echo "   ✅ Payment server (puerto 5002) PID=$!"

nohup python3 app/dashboard/app.py > /tmp/dashboard.log 2>&1 &
echo "   ✅ Dashboard (puerto 5000) PID=$!"

nohup python3 runner.py --daemon > /tmp/runner-daemon.log 2>&1 &
echo "   ✅ Runner daemon PID=$!"

# 8. Resumen
echo ""
echo "=========================================="
echo "✅ CodeAudit Pro desplegado"
echo "=========================================="
echo ""
echo "   📊 Dashboard:  http://localhost:5000"
echo "   💳 Pagos:      http://localhost:5002"
echo "   📝 Landing:    http://localhost:5001"
echo "   🤖 Runner:     Daemon activo"
echo ""
echo "   Logs:"
echo "     tail -f /tmp/landing_handler.log"
echo "     tail -f /tmp/payment.log"
echo "     tail -f /tmp/dashboard.log"
echo "     tail -f /tmp/runner-daemon.log"
echo ""
echo "   Para producción, configura un proxy inverso (nginx) y"
echo "   systemd services en lugar de nohup. Ver README.md"
echo "=========================================="

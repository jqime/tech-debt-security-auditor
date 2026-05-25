#!/bin/bash
set -e

# Master Script for Tech Debt & Security Auditor
# Usage: ./run-audit.sh [repo_url_or_local_path] [model]

TARGET=${1:-"https://github.com/octocat/Hello-World"}
MODEL=${2:-"opencode/deepseek-v4-flash-free"}

# Establish absolute directory path of the script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=========================================================="
echo "🛡️  INICIANDO ASISTENTE DE AUDITORÍA DE SEGURIDAD Y CALIDAD"
echo "=========================================================="

# Check if target is a git URL or a local path
if [[ "$TARGET" =~ ^https?:// ]] || [[ "$TARGET" =~ ^git@ ]]; then
    TEMP_DIR="/tmp/test-repo"
    echo "🌐 Clonando repositorio remoto: $TARGET..."
    
    # Clean up previous runs
    rm -rf "$TEMP_DIR"
    
    # Clone the repo
    git clone --depth 1 "$TARGET" "$TEMP_DIR"
    AUDIT_PATH="$TEMP_DIR"
else
    AUDIT_PATH="$TARGET"
fi

# Ensure reports directory exists
mkdir -p "$SCRIPT_DIR/reports"

# Execute the runner script
python3 "$SCRIPT_DIR/scripts/run.sh" "$AUDIT_PATH" "$MODEL"

echo "=========================================================="
echo "📊 AUDITORÍA COMPLETA Y FINALIZADA"
echo "👉 Reporte ejecutivo disponible en:"
echo "   $SCRIPT_DIR/reports/executive-report.html"
echo "=========================================================="

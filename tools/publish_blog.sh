#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$SCRIPT_DIR"

echo "📝 Publicando blog de CodeAudit Pro..."
echo ""

# Verificar que hay cambios en app/blog/
if git diff --stat --cached app/blog/ | grep -q "blog/" || [[ -n $(git status --porcelain app/blog/) ]]; then
    git add app/blog/
    git commit -m "Actualización automática del blog - $(date +'%Y-%m-%d %H:%M')"
    echo "✓ Blog actualizado y commiteado."
else
    echo "ℹ️ No hay cambios nuevos en app/blog/."
fi

# Preguntar si hacer push
read -p "¿Deseas hacer push a GitHub? (s/n): " confirm
if [[ "$confirm" == "s" ]]; then
    git push origin main
    echo "✓ Push completado."
else
    echo "ℹ️ Push omitido. Los cambios están en el commit local."
fi

echo ""
echo "📎 URL del blog: https://github.com/jqime/tech-debt-security-auditor/blob/main/app/blog/index.html"

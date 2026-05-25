#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

TARGET=${1:-"https://github.com/octocat/Hello-World"}
MODEL=${2:-"opencode/deepseek-v4-flash-free"}
AUDIT_ID=$(uuidgen 2>/dev/null || python3 -c "import uuid;print(uuid.uuid4())" 2>/dev/null || date +%s)
TEMP_DIR="/tmp/codeaudit-$AUDIT_ID"

echo "=========================================================="
echo "🛡️  CodeAudit Pro — Auditoría #$AUDIT_ID"
echo "=========================================================="

if [[ "$TARGET" =~ ^https?:// ]] || [[ "$TARGET" =~ ^git@ ]]; then
    echo "🌐 Clonando: $TARGET"
    git clone --depth 1 "$TARGET" "$TEMP_DIR"
    AUDIT_PATH="$TEMP_DIR"
else
    AUDIT_PATH="$TARGET"
fi

mkdir -p "$SCRIPT_DIR/reports"

python3 "$SCRIPT_DIR/engine/run.py" "$AUDIT_PATH" "$MODEL" --audit-id "$AUDIT_ID"

rm -rf "$TEMP_DIR"

echo "=========================================================="
echo "📊 AUDITORÍA COMPLETA — ID: $AUDIT_ID"
echo "👉 reports/executive-report.html"
echo "=========================================================="

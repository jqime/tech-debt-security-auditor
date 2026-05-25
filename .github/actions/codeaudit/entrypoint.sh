#!/bin/sh
set -e

REPO_URL="${1:-}"
MODEL="${2:-opencode/deepseek-v4-flash-free}"
COMMENT_PR="${3:-true}"
GITHUB_TOKEN="${4:-}"

echo "=========================================================="
echo "🛡️  CodeAudit Pro — GitHub Action"
echo "=========================================================="
echo "Repositorio: ${REPO_URL:-$(pwd)}"
echo "Modelo:      $MODEL"
echo "Comentar PR: $COMMENT_PR"
echo ""

# Si no hay URL, usar el repositorio actual (checkeado en /github/workspace)
if [ -z "$REPO_URL" ]; then
    TARGET="."
    echo "📂 Usando repositorio actual"
else
    TARGET="/tmp/repo-to-audit"
    echo "🌐 Clonando: $REPO_URL"
    git clone --depth 1 "$REPO_URL" "$TARGET"
fi

# Verificar que opencode está disponible
if ! command -v opencode >/dev/null 2>&1; then
    echo "⚠️  opencode no encontrado. Instalando..."
    npm install -g opencode-ai
fi

# Ejecutar escaneo de seguridad
echo ""
echo "🔒 [1/2] Escaneo de seguridad..."
SEC_PROMPT="Analiza el repositorio en '${TARGET:-.}'. Busca secretos expuestos (API keys, tokens, passwords) y dependencias vulnerables. Devuelve SOLO un JSON sin texto adicional: {\"secrets\": [{\"file\": \"...\", \"line\": 123, \"reason\": \"...\"}], \"vulnerable_dependencies\": [{\"name\": \"...\", \"version\": \"...\", \"severity\": \"HIGH\"}]}"

SEC_OUTPUT=$(opencode run -m "$MODEL" --dangerously-skip-permissions "$SEC_PROMPT" 2>/dev/null || echo '{"secrets":[],"vulnerable_dependencies":[]}')
echo "$SEC_OUTPUT" > reports/security-report.json
echo "✓ Escaneo completado"

# Ejecutar medición de deuda
echo ""
echo "📊 [2/2] Medición de deuda técnica..."
DEBT_PROMPT="Analiza el repositorio en '${TARGET:-.}'. Mide complejidad ciclomática promedio y líneas duplicadas. Devuelve SOLO un JSON: {\"average_complexity\": 0.0, \"duplicated_lines\": 0}"

DEBT_OUTPUT=$(opencode run -m "$MODEL" --dangerously-skip-permissions "$DEBT_PROMPT" 2>/dev/null || echo '{"average_complexity":"N/A","duplicated_lines":0}')
echo "$DEBT_OUTPUT" > reports/debt-report.json
echo "✓ Medición completada"

# Generar informe HTML básico
echo ""
echo "🎨 Generando informe HTML..."
REPORT_FILE="reports/executive-report.html"

SECRETS_COUNT=$(echo "$SEC_OUTPUT" | jq -r '.secrets | length' 2>/dev/null || echo "0")
VULN_COUNT=$(echo "$SEC_OUTPUT" | jq -r '.vulnerable_dependencies | length' 2>/dev/null || echo "0")
COMPLEXITY=$(echo "$DEBT_OUTPUT" | jq -r '.average_complexity' 2>/dev/null || echo "N/A")
DUPLICATED=$(echo "$DEBT_OUTPUT" | jq -r '.duplicated_lines' 2>/dev/null || echo "0")

mkdir -p reports
cat > "$REPORT_FILE" << HTML
<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8"><title>CodeAudit Pro - Informe</title>
<style>
  body { font-family: system-ui; background: #0b0f19; color: #f8fafc; padding: 2rem; max-width: 800px; margin: 0 auto; }
  h1 { color: #818cf8; }
  .card { background: #131b2e; border: 1px solid #1e293b; border-radius: 12px; padding: 1.5rem; margin: 1rem 0; }
  .metric { font-size: 2rem; font-weight: 800; color: #6366f1; }
  .label { color: #94a3b8; font-size: 0.9rem; }
  .danger { color: #f43f5e; }
  .ok { color: #10b981; }
</style></head>
<body>
  <h1>🛡️ CodeAudit Pro</h1>
  <p style="color: #94a3b8;">Auditoría ejecutada el $(date)</p>
  <div class="card">
    <h2>🔒 Secretos encontrados: <span class="metric $([ "$SECRETS_COUNT" -gt 0 ] && echo 'danger' || echo 'ok')">$SECRETS_COUNT</span></h2>
    <h2>📦 Vulnerabilidades: <span class="metric $([ "$VULN_COUNT" -gt 0 ] && echo 'danger' || echo 'ok')">$VULN_COUNT</span></h2>
  </div>
  <div class="card">
    <h2>📊 Deuda Técnica</h2>
    <p>Complejidad ciclomática media: <strong>$COMPLEXITY</strong></p>
    <p>Líneas duplicadas: <strong>$DUPLICATED</strong></p>
  </div>
  <hr style="border-color: #1e293b;">
  <p style="color: #64748b;">Generado por CodeAudit Pro — https://github.com/jqime/tech-debt-security-auditor</p>
</body></html>
HTML
echo "✓ Informe generado: $REPORT_FILE"

# Comentar en PR si aplica
if [ "$COMMENT_PR" = "true" ] && [ -n "$GITHUB_TOKEN" ] && [ -n "$GITHUB_REPOSITORY" ] && [ -n "$GITHUB_EVENT_NAME" ] && [ "$GITHUB_EVENT_NAME" = "pull_request" ]; then
    PR_NUMBER=$(echo "$GITHUB_EVENT_PATH" | xargs cat 2>/dev/null | jq -r '.number // empty' 2>/dev/null)
    if [ -n "$PR_NUMBER" ]; then
        echo ""
        echo "💬 Comentando hallazgos en PR #$PR_NUMBER..."
        COMMENT="## 🛡️ CodeAudit Pro - Resultados de la auditoría\n\n"
        COMMENT="${COMMENT}**🔒 Secretos:** $SECRETS_COUNT encontrados\n"
        COMMENT="${COMMENT}**📦 Vulnerabilidades:** $VULN_COUNT encontradas\n"
        COMMENT="${COMMENT}**📊 Complejidad media:** $COMPLEXITY\n"
        COMMENT="${COMMENT}**🔁 Líneas duplicadas:** $DUPLICATED\n\n"
        if [ "$SECRETS_COUNT" -gt 0 ] || [ "$VULN_COUNT" -gt 0 ]; then
            COMMENT="${COMMENT}⚠️ **Se encontraron problemas que requieren atención.**\n"
        else
            COMMENT="${COMMENT}✅ **No se encontraron problemas críticos.**\n"
        fi
        COMMENT="${COMMENT}\n_Informe completo disponible como artefacto de la acción._"

        curl -s -X POST \
            -H "Authorization: token $GITHUB_TOKEN" \
            -H "Content-Type: application/json" \
            -d "$(echo "{\"body\": \"$COMMENT\"}" | jq -R -s '{body: .}')" \
            "https://api.github.com/repos/$GITHUB_REPOSITORY/issues/$PR_NUMBER/comments" \
            2>/dev/null && echo "✓ Comentario publicado" || echo "⚠️ No se pudo comentar"
    fi
fi

echo ""
echo "=========================================================="
echo "✅ AUDITORÍA COMPLETADA"
echo "   Secretos: $SECRETS_COUNT"
echo "   Vulnerabilidades: $VULN_COUNT"
echo "   Complejidad: $COMPLEXITY"
echo "   Informe: $REPORT_FILE"
echo "=========================================================="

# Output for GitHub Actions
echo "secrets_count=$SECRETS_COUNT" >> "$GITHUB_OUTPUT"
echo "vulnerabilities_count=$VULN_COUNT" >> "$GITHUB_OUTPUT"

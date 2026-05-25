#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=========================================="
echo "🧪 Test Compliance — CodeAudit Pro"
echo "=========================================="
echo ""

# 1. Auditoría de ejemplo
echo "📡 [1/5] Ejecutando auditoría de ejemplo..."
./run-audit.sh https://github.com/octocat/Hello-World

# 2. Informe de cumplimiento NIS2/DORA
echo ""
echo "📋 [2/5] Generando informe de cumplimiento NIS2/DORA..."
python3 compliance_report.py

# 3. Certificación blockchain
echo ""
echo "🔏 [3/5] Certificando integridad del informe..."
python3 certify.py --certify

# 4. Resumen
echo ""
echo "📊 [4/5] Resumen de cumplimiento..."
echo ""
if [ -f reports/compliance-nis2.html ]; then
    SCORE=$(grep -oP 'overall-score[^>]*>(\d+)' reports/compliance-nis2.html 2>/dev/null | grep -oP '\d+' || echo "N/A")
    echo "   Score de cumplimiento global: $SCORE/100"
fi
echo ""

# 5. Mostrar archivos generados
echo "📁 [5/5] Archivos generados:"
echo ""
echo "   📈 Informe técnico:      reports/executive-report.html"
echo "   📋 Compliance NIS2/DORA: reports/compliance-nis2.html"
echo "   🔏 Hash log:             reports/hashes.log"
echo "   📱 QR verificación:      reports/verify-qr.png"
echo ""

# Mostrar hash
if [ -f reports/hashes.log ]; then
    echo "   🔐 Último hash registrado:"
    tail -1 reports/hashes.log
fi

echo ""
echo "=========================================="
echo "✅ Test Compliance completado"
echo "=========================================="
echo ""
echo "   Para abrir los informes:"
echo "   open reports/executive-report.html"
echo "   open reports/compliance-nis2.html"
echo ""

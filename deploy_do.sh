#!/bin/bash
set -e

# ═══════════════════════════════════════════════════════════════════
# 🚀 CodeAudit Pro — Deploy a DigitalOcean Droplet
# ═══════════════════════════════════════════════════════════════════
# Uso: ./deploy_do.sh <do_token> <droplet_name> [domain]
# Ej:  ./deploy_do.sh dop_v1_xxx codeaudit-pro codeauditpro.com
# ═══════════════════════════════════════════════════════════════════

DO_TOKEN=${1:-""}
DROPLET_NAME=${2:-"codeaudit-pro"}
DOMAIN=${3:-""}

if [ -z "$DO_TOKEN" ]; then
    echo "❌ Uso: ./deploy_do.sh <do_token> <droplet_name> [domain]"
    echo "   DO_TOKEN requerido. Consíguelo en https://cloud.digitalocean.com/account/api/tokens"
    exit 1
fi

echo "═══════════════════════════════════════════════════════════════"
echo "  🚀 CodeAudit Pro — Deploy en DigitalOcean"
echo "═══════════════════════════════════════════════════════════════"

# ── 1. Crear Droplet ──────────────────────────────────────────────
echo ""
echo "📡 [1/6] Creando droplet: $DROPLET_NAME..."

SSH_KEY_ID=$(curl -s -X GET "https://api.digitalocean.com/v2/account/keys" \
  -H "Authorization: Bearer $DO_TOKEN" | python3 -c "import json,sys; keys=json.load(sys.stdin)['ssh_keys']; print(keys[0]['id'] if keys else '')" 2>/dev/null || echo "")

CREATE_PAYLOAD=$(cat <<EOF
{
  "name": "$DROPLET_NAME",
  "region": "fra1",
  "size": "s-2vcpu-4gb",
  "image": "docker-20-04",
  "monitoring": true,
  "tags": ["codeaudit-pro"]
}
EOF
)

if [ -n "$SSH_KEY_ID" ]; then
    CREATE_PAYLOAD=$(echo "$CREATE_PAYLOAD" | python3 -c "
import json,sys
p = json.load(sys.stdin)
p['ssh_keys'] = [$SSH_KEY_ID]
print(json.dumps(p))
")
fi

DROPLET_RESP=$(curl -s -X POST "https://api.digitalocean.com/v2/droplets" \
  -H "Authorization: Bearer $DO_TOKEN" \
  -H "Content-Type: application/json" \
  -d "$CREATE_PAYLOAD")

DROPLET_ID=$(echo "$DROPLET_RESP" | python3 -c "import json,sys; print(json.load(sys.stdin)['droplet']['id'])" 2>/dev/null || echo "")

if [ -z "$DROPLET_ID" ]; then
    echo "❌ Error creando droplet:"
    echo "$DROPLET_RESP"
    exit 1
fi

echo "   ✅ Droplet creado (ID: $DROPLET_ID)"
echo "   ⏳ Esperando IP pública..."

# ── 2. Esperar IP ──────────────────────────────────────────────────
sleep 30
for i in $(seq 1 20); do
    IP=$(curl -s -X GET "https://api.digitalocean.com/v2/droplets/$DROPLET_ID" \
      -H "Authorization: Bearer $DO_TOKEN" | \
      python3 -c "import json,sys; d=json.load(sys.stdin)['droplet']; ips=[n['ip_address'] for n in d['networks']['v4'] if n['type']=='public']; print(ips[0] if ips else '')" 2>/dev/null)
    if [ -n "$IP" ]; then
        echo "   ✅ IP: $IP"
        break
    fi
    echo "   Esperando... ($i/20)"
    sleep 10
done

if [ -z "$IP" ]; then
    echo "❌ No se pudo obtener la IP"
    exit 1
fi

# ── 3. Esperar SSH ────────────────────────────────────────────────
echo ""
echo "🔑 [2/6] Esperando conexión SSH..."
for i in $(seq 1 30); do
    if ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 "root@$IP" "echo ready" 2>/dev/null; then
        echo "   ✅ SSH conectado"
        break
    fi
    if [ "$i" -eq 30 ]; then
        echo "❌ No se pudo conectar SSH"
        exit 1
    fi
    echo "   Esperando... ($i/30)"
    sleep 5
done

# ── 4. Configurar dominio (opcional) ──────────────────────────────
if [ -n "$DOMAIN" ]; then
    echo ""
    echo "🌐 [3/6] Configurando dominio: $DOMAIN..."
    ssh root@$IP "apt-get update -qq && apt-get install -y -qq caddy 2>/dev/null" || true
    ssh root@$IP "cat > /etc/caddy/Caddyfile << 'CADDYEOF'
$DOMAIN {
    reverse_proxy localhost:5000
}

api.$DOMAIN {
    reverse_proxy localhost:5001
}

pay.$DOMAIN {
    reverse_proxy localhost:5002
}
CADDYEOF
systemctl enable caddy 2>/dev/null || true
systemctl restart caddy 2>/dev/null || true"
    echo "   ✅ Caddy configurado con SSL automático"
fi

# ── 5. Subir y desplegar con Docker ────────────────────────────────
echo ""
echo "📦 [4/6] Subiendo código al droplet..."
rsync -avz --exclude '.git' --exclude '__pycache__' --exclude '.venv' \
  -e "ssh -o StrictHostKeyChecking=no" \
  ./ "root@$IP:/opt/codeaudit-pro/"

echo ""
echo "🐳 [5/6] Construyendo y arrancando con Docker Compose..."
ssh root@$IP "cd /opt/codeaudit-pro && docker compose build && docker compose up -d"

# ── 6. Health check ────────────────────────────────────────────────
echo ""
echo "🏥 [6/6] Verificando servicios..."
sleep 10
for i in $(seq 1 12); do
    STATUS=$(curl -s -o /dev/null -w "%{http_code}" "http://$IP:5000/" 2>/dev/null || echo "000")
    if [ "$STATUS" = "200" ] || [ "$STATUS" = "302" ]; then
        echo "   ✅ Dashboard respondiendo (HTTP $STATUS)"
        break
    fi
    echo "   Esperando... ($i/12)"
    sleep 5
done

# ── Resumen ────────────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  ✅ CodeAudit Pro desplegado en DigitalOcean"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "   📊 Dashboard: http://$IP:5000"

if [ -n "$DOMAIN" ]; then
    echo "   🌐 Web:       https://$DOMAIN"
    echo "   🔌 API:       https://api.$DOMAIN"
    echo "   💳 Pagos:     https://pay.$DOMAIN"
fi

echo ""
echo "   SSH:          ssh root@$IP"
echo "   Logs:         ssh root@$IP 'docker compose -f /opt/codeaudit-pro/docker-compose.yml logs -f'"
echo ""
echo "   ⚠️  Próximos pasos:"
echo "     1. ssh root@$IP y ejecuta: cd /opt/codeaudit-pro && cp .env.example .env"
echo "     2. Edita .env con tus claves (STRIPE, EMAIL, etc.)"
echo "     3. docker compose restart"
echo ""
echo "═══════════════════════════════════════════════════════════════"

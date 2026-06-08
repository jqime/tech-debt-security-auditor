#!/bin/bash
# ──────────────────────────────────────────────────────────────
#  CodeAudit Pro — Despliegue Producción (Docker + Nginx + SSL)
#  Uso: sudo bash deploy/production_deploy.sh
# ──────────────────────────────────────────────────────────────
set -euo pipefail

DOMAIN="${DOMAIN:-codeauditpro.com}"
ADMIN_EMAIL="${ADMIN_EMAIL:-admin@codeauditpro.com}"
PROJECT_SRC="$(cd "$(dirname "$0")/.." && pwd)"
INSTALL_DIR="/opt/codeauditpro"
DEPLOY_DIR="$PROJECT_SRC/deploy"
NGINX_AVAILABLE="/etc/nginx/sites-available"
NGINX_ENABLED="/etc/nginx/sites-enabled"
COMPOSE_PROJECT="codeauditpro"

# ── Colores ──────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; NC='\033[0m'
info()  { echo -e "${CYAN}ℹ️${NC} $1"; }
ok()    { echo -e "${GREEN}✅${NC} $1"; }
warn()  { echo -e "${YELLOW}⚠️${NC} $1"; }
err()   { echo -e "${RED}❌${NC} $1"; }

# ── Root check ───────────────────────────────────────────────
if [[ $EUID -ne 0 ]]; then
    err "Este script debe ejecutarse como root (sudo)"
    exit 1
fi

echo ""
echo -e "${CYAN}==========================================${NC}"
echo -e "${CYAN}  🚀 CodeAudit Pro — Despliegue Producción${NC}"
echo -e "${CYAN}==========================================${NC}"
echo ""

# ── 1. Dependencias del sistema ─────────────────────────────
info "Instalando dependencias del sistema..."
if command -v apt-get &>/dev/null; then
    apt-get update -qq
    apt-get install -y -qq docker.io docker-compose-plugin nginx certbot python3-certbot-nginx curl
elif command -v yum &>/dev/null; then
    yum install -y docker docker-compose nginx certbot python3-certbot-nginx curl
else
    err "SO no soportado. Usa Debian/Ubuntu o CentOS/RHEL."
    exit 1
fi
ok "Dependencias instaladas"

# ── 2. Copiar código ────────────────────────────────────────
info "Instalando código en $INSTALL_DIR..."
if [[ "$PROJECT_SRC" != "$INSTALL_DIR" ]]; then
    if [[ -d "$INSTALL_DIR" ]]; then
        warn "Directorio $INSTALL_DIR ya existe. Haciendo backup..."
        mv "$INSTALL_DIR" "${INSTALL_DIR}.bak.$(date +%s)"
    fi
    cp -a "$PROJECT_SRC" "$INSTALL_DIR"
fi
cd "$INSTALL_DIR"
ok "Código instalado en $INSTALL_DIR"

# ── 3. Variables de entorno ─────────────────────────────────
if [[ ! -f .env ]]; then
    warn "No se encontró .env. Creando desde .env.example..."
    cp .env.example .env
    echo -e "${YELLOW}⚠️  EDITAR .env ANTES DE CONTINUAR:${NC}"
    echo "   nano $INSTALL_DIR/.env"
    echo "   Luego pulsa Enter para continuar, o Ctrl+C para salir"
    read -r
fi

# ── 4. Cifrado del .env ─────────────────────────────────────
if [[ ! -f /etc/codeaudit.key ]]; then
    info "Generando clave maestra para cifrado de .env..."
    mkdir -p /etc/codeaudit
    openssl rand -base64 32 > /etc/codeaudit.key
    chmod 400 /etc/codeaudit.key
    openssl enc -aes-256-cbc -salt -in .env -out .env.enc -pass file:/etc/codeaudit.key
    ok "Archivo .env cifrado como .env.enc"
fi

# ── 5. Levantar contenedores Docker ─────────────────────────
info "Construyendo y levantando contenedores Docker..."
docker compose -p "$COMPOSE_PROJECT" down --remove-orphans 2>/dev/null || true
docker compose -p "$COMPOSE_PROJECT" up -d --build
ok "Contenedores Docker levantados"

# ── 6. Configurar Nginx ──────────────────────────────────
info "Configurando Nginx..."
NGINX_CONF="$NGINX_AVAILABLE/codeauditpro"
if [[ -f "$DEPLOY_DIR/codeauditpro.nginx" ]]; then
    cp "$DEPLOY_DIR/codeauditpro.nginx" "$NGINX_CONF"
    sed -i "s/codeauditpro.com/$DOMAIN/g" "$NGINX_CONF"
    sed -i "s|/opt/codeauditpro|$INSTALL_DIR|g" "$NGINX_CONF"

    if [[ ! -L "$NGINX_ENABLED/codeauditpro" ]]; then
        ln -sf "$NGINX_CONF" "$NGINX_ENABLED/codeauditpro"
    fi
    ok "Configuración Nginx instalada para $DOMAIN"
fi

# ── 7. Certificado SSL (Let's Encrypt) ──────────────────────
if [[ ! -f "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" ]]; then
    info "Solicitando certificado SSL para $DOMAIN..."
    certbot --nginx -d "$DOMAIN" -d "*.$DOMAIN" --non-interactive --agree-tos -m "$ADMIN_EMAIL" || {
        warn "No se pudo obtener SSL automáticamente. Ejecuta manualmente:"
        echo "  certbot --nginx -d $DOMAIN -d *.$DOMAIN"
    }
else
    ok "Certificado SSL ya existe para $DOMAIN"
fi

# ── 8. Verificar Nginx ──────────────────────────────────────
nginx -t && ok "Configuración Nginx válida" || err "Nginx tiene errores de sintaxis"

# ── 9. Recargar Nginx ───────────────────────────────────────
systemctl reload nginx 2>/dev/null || systemctl restart nginx
ok "Nginx recargado"

# ── 10. Health check ────────────────────────────────────────
echo ""
info "Verificando estado de los contenedores..."
sleep 3
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

echo ""
info "Verificando accesibilidad HTTP..."
for port in 5000 5001 5002 5003; do
    code=$(curl -so /dev/null -w '%{http_code}' "http://127.0.0.1:$port" 2>/dev/null || echo "000")
    if [[ "$code" != "000" ]]; then
        ok "  Puerto $port → HTTP $code"
    else
        err "  Puerto $port → SIN RESPUESTA"
    fi
done

echo ""
echo -e "${GREEN}==========================================${NC}"
echo -e "${GREEN}  🎉 CodeAudit Pro desplegado en producción${NC}"
echo -e "${GREEN}==========================================${NC}"
echo ""
echo "   🌐 Sitio:       https://$DOMAIN/"
echo "   📊 Dashboard:   https://$DOMAIN/dashboard/"
echo "   💳 Pagos:       https://$DOMAIN/api/payments/"
echo "   🤖 Webhooks:    https://$DOMAIN/webhook/github"
echo ""
echo "   📝 Logs:"
echo "     docker logs -f ${COMPOSE_PROJECT}-dashboard-1"
echo "     docker logs -f ${COMPOSE_PROJECT}-landing-1"
echo "     docker logs -f ${COMPOSE_PROJECT}-payment-1"
echo "     docker logs -f ${COMPOSE_PROJECT}-continuous-audit-1"
echo "     docker logs -f ${COMPOSE_PROJECT}-runner-1"
echo ""
echo "   🔄 Actualizar:  docker compose -p $COMPOSE_PROJECT pull && docker compose -p $COMPOSE_PROJECT up -d"
echo ""

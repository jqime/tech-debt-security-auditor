#!/bin/bash
# ──────────────────────────────────────────────────────────────
#  CodeAudit Pro — Despliegue Producción (Systemd + Nginx + SSL)
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
SYSTEMD_DIR="/etc/systemd/system"
SERVICES=(
    "codeaudit-dashboard"
    "codeaudit-landing"
    "codeaudit-payments"
    "codeaudit-continuous"
)

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
    apt-get install -y -qq python3 python3-pip python3-venv git nginx certbot python3-certbot-nginx openssl curl
elif command -v yum &>/dev/null; then
    yum install -y python3 python3-pip git nginx certbot python3-certbot-nginx openssl curl
else
    err "SO no soportado. Usa Debian/Ubuntu o CentOS/RHEL."
    exit 1
fi
ok "Dependencias instaladas"

# ── 2. Clonar / copiar código ────────────────────────────────
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

# ── 3. Entorno virtual y dependencias Python ─────────────────
info "Configurando entorno virtual Python..."
if [[ ! -d venv ]]; then
    python3 -m venv venv
fi
source venv/bin/activate
pip install -q --upgrade pip
pip install -q -r requirements.txt
deactivate
ok "Dependencias Python instaladas"

# ── 4. Variables de entorno ──────────────────────────────────
if [[ ! -f .env ]]; then
    warn "No se encontró .env. Creando desde .env.example..."
    cp .env.example .env
    echo -e "${YELLOW}⚠️  EDITAR .env ANTES DE CONTINUAR:${NC}"
    echo "   nano $INSTALL_DIR/.env"
    echo "   Luego ejecuta: sudo systemctl daemon-reload && sudo systemctl restart codeaudit-dashboard"
    echo "   (pulsa Enter cuando hayas configurado .env, o Ctrl+C para salir)"
    read -r
fi

# ── 5. Cifrado del .env (opcional) ──────────────────────────
if [[ ! -f /etc/codeaudit.key ]]; then
    info "Generando clave maestra para cifrado de .env..."
    mkdir -p /etc/codeaudit
    openssl rand -base64 32 > /etc/codeaudit.key
    chmod 400 /etc/codeaudit.key
    openssl enc -aes-256-cbc -salt -in .env -out .env.enc -pass file:/etc/codeaudit.key
    ok "Archivo .env cifrado como .env.enc"
fi

# ── 6. Instalar systemd services ─────────────────────────────
info "Instalando servicios systemd..."
for svc in "${SERVICES[@]}"; do
    src="$DEPLOY_DIR/$svc.service"
    if [[ -f "$src" ]]; then
        # Modificar WorkingDirectory al install_dir real
        sed "s|/opt/codeauditpro|$INSTALL_DIR|g" "$src" > "$SYSTEMD_DIR/$svc.service"

        # Añadir LoadCredential si existe .env.enc
        if [[ -f "$INSTALL_DIR/.env.enc" ]]; then
            cat >> "$SYSTEMD_DIR/$svc.service" <<EOF

# ── .env cifrado en RAM ──
ExecStartPre=/bin/sh -c "/usr/bin/openssl enc -d -aes-256-cbc -in $INSTALL_DIR/.env.enc -out /run/codeaudit/.env -pass file:/etc/codeaudit.key 2>/dev/null; mkdir -p /run/codeaudit"
RuntimeDirectory=codeaudit
EnvironmentFile=/run/codeaudit/.env
EOF
        fi

        chmod 644 "$SYSTEMD_DIR/$svc.service"
        ok "  $svc.service instalado"
    else
        warn "  $svc.service no encontrado en $src"
    fi
done

# ── 7. Instalar configuración Nginx ──────────────────────────
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

# ── 8. Certificado SSL (Let's Encrypt) ───────────────────────
if [[ ! -f "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" ]]; then
    info "Solicitando certificado SSL para $DOMAIN..."
    certbot --nginx -d "$DOMAIN" -d "*.$DOMAIN" --non-interactive --agree-tos -m "$ADMIN_EMAIL" || {
        warn "No se pudo obtener SSL automáticamente. Ejecuta manualmente:"
        echo "  certbot --nginx -d $DOMAIN -d *.$DOMAIN"
    }
else
    ok "Certificado SSL ya existe para $DOMAIN"
fi

# ── 9. Verificar Nginx ───────────────────────────────────────
nginx -t && ok "Configuración Nginx válida" || err "Nginx tiene errores de sintaxis"

# ── 10. Activar e iniciar servicios ──────────────────────────
info "Arrancando servicios..."
systemctl daemon-reload

for svc in "${SERVICES[@]}"; do
    systemctl enable --now "$svc" 2>/dev/null && ok "  $svc activo" || warn "  $svc falló al arrancar"
done

systemctl reload nginx 2>/dev/null || systemctl restart nginx
ok "Nginx recargado"

# ── 11. Health check ─────────────────────────────────────────
echo ""
info "Verificando estado de los servicios..."
sleep 2
for svc in "${SERVICES[@]}"; do
    if systemctl is-active --quiet "$svc"; then
        ok "  $svc  →  activo"
    else
        err "  $svc  →  INACTIVO (logs: journalctl -u $svc -n 50)"
    fi
done

echo ""
echo -e "${GREEN}==========================================${NC}"
echo -e "${GREEN}  🎉 CodeAudit Pro desplegado en producción${NC}"
echo -e "${GREEN}==========================================${NC}"
echo ""
echo "   📊 Dashboard:  https://$DOMAIN/"
echo "   💳 Pagos:      https://$DOMAIN/api/payments/"
echo "   🤖 Webhooks:   https://$DOMAIN/webhook/github"
echo ""
echo "   📝 Logs:"
echo "     journalctl -u codeaudit-dashboard -f"
echo "     journalctl -u codeaudit-landing -f"
echo "     journalctl -u codeaudit-payments -f"
echo "     journalctl -u codeaudit-continuous -f"
echo ""

# ── Runner daemon independiente ──────────────────────────────
info "El Runner daemon se ejecuta junto al dashboard."
echo "   Para lanzar el worker manual:"
echo "     cd $INSTALL_DIR && source venv/bin/activate && python3 runner.py --daemon"
echo ""

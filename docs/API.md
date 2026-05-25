# API — CodeAudit Pro

Documentación de los endpoints públicos y privados. Próximamente disponible una especificación OpenAPI 3.0 completa.

## Endpoints Actuales

### `POST /create-checkout-session`
Crea una sesión de pago en Stripe.

**Body:** `{ "price_id": "auditoria_unica", "repo_url": "...", "customer_email": "..." }`

### `POST /stripe-webhook`
Webhook de Stripe para notificaciones de pago.

### `POST /webhook/github`
Webhook de GitHub para auditoría continua (push / pull_request).

### `GET /compliance-scores`
Devuelve histórico de scores de cumplimiento.

### `POST /save-compliance`
Guarda scores de cumplimiento de una auditoría.

### `POST /my-company/save`
Guarda configuración white-label del cliente.

### `GET /whitelabel/<client_id>`
Devuelve configuración white-label de un cliente.

---

## Próximamente

- API REST pública con autenticación JWT.
- SDK en Python y JavaScript.
- Webhooks de salida para eventos de auditoría.

# 🛡️ CodeAudit Pro — Plan de Negocio

## 1. Estrategia de Precios

| Producto | Precio | Descripción |
|----------|--------|-------------|
| Informe gratuito | 0 € | Muestra de capacidades (1 repo público, escaneo básico) |
| Auditoría única | 299 € | Auditoría completa con informe HTML premium |
| Suscripción mensual | 199 €/mes | Hasta 4 auditorías, dashboard, alertas continuas |

### Justificación de precios
- **Benchmark**: Herramientas como SonarQube Cloud (gratis limitado, ~150 €/mes equipo), Snyk (~200 €/mes), Black Duck (~miles €/año).
- **Valor**: Por 299 € el cliente obtiene un diagnóstico que le evitaría pérdidas de 3.000-30.000 € en incidentes.
- **PYME-friendly**: Sin compromiso anual, pago por uso o suscripción cancelable.

## 2. Estructura de Costes

| Concepto | Coste | Notas |
|----------|-------|-------|
| OpenCode | 0 € | Modelo gratuito deepseek-v4-flash-free |
| Servidor VPS mínimo | ~5-10 €/mes | Para el dashboard y runner |
| Dominio | ~10 €/año | codeauditpro.es o similar |
| Stripe (comisiones) | 1.4% + 0.25 € | Por transacción |
| Gmail SMTP | 0 € | Hasta 500 emails/día (gratuito) |
| Google Maps API | ~0 € | Uso mínimo en prospección (200 $ gratis/mes) |

### Margen por auditoría (299 €)
| Concepte | Importe |
|----------|---------|
| Ingreso | 299,00 € |
| Comisión Stripe (1.4% + 0.25 €) | -4,44 € |
| Coste servidor (prorrateado) | -0,33 € |
| **Margen bruto** | **~294 €** |
| **Margen %** | **~98,3 %** |

### Margen suscripción mensual (199 €/mes)
| Concept | Importe |
|---------|---------|
| Ingreso | 199,00 € |
| Comisión Stripe | -3,04 € |
| Coste servidor (prorrateado) | -0,33 € |
| **Margen bruto** | **~196 €** |
| **Margen %** | **~98,3 %** |

## 3. Proyección de Ingresos

| Escenario | Clientes/mes | Ingreso mensual | Ingreso anual |
|-----------|-------------|----------------|---------------|
| Mínimo (5 audits únicas) | 5 | 1.495 € | 17.940 € |
| Moderado (3 únicas + 5 suscripciones) | 8 | 1.892 € | 22.704 € |
| Bueno (5 únicas + 10 suscripciones) | 15 | 3.485 € | 41.820 € |
| Excelente (10 únicas + 20 suscripciones) | 30 | 6.970 € | 83.640 € |

## 4. Cómo Conseguir los Primeros 10 Clientes

### Semana 1-2: Preparación
- [ ] Crear perfil de LinkedIn destacando el servicio.
- [ ] Preparar el informe de muestra gratuito como lead magnet.
- [ ] Tener la landing page operativa.

### Semana 3-4: Prospección activa
1. **LinkedIn** (5 clientes potenciales):
   - Conectar con CTOs/Developers de PYMES tecnológicas españolas.
   - Compartir el informe gratuito en grupos de desarrollo/startups.
   - Publicar casos prácticos: "Encontramos 3 API keys expuestas en una PYME de ecommerce".

2. **Foros y comunidades** (3 clientes potenciales):
   - Participar en r/SpainDev, r/programacion, r/SpainStartups.
   - Ofrecer auditorías gratuitas a cambio de testimonios.
   - Escribir en Medium/dev.to sobre "Cómo auditar tu código gratis".

3. **Networking directo** (2 clientes potenciales):
   - Asistir a meetups de tecnología locales.
   - Ofrecer demo en persona a agencias digitales conocidas.
   - Contactar incubadoras de startups (Google for Startups, Wayra, Lanzadera).

### Semana 5-6: Cierre
- Seguimiento personalizado a cada lead.
- Ofrecer descuento por lanzamiento (primera auditoría 199 €).
- Recoger testimonios y casos de éxito para web.

## 5. Automatización del Embudo

```
Prospección (prospect.py) → Leads en CSV
       ↓
Email outreach (email_sender.py) → Informe gratuito
       ↓
Landing page → Checkout Stripe (payment.py)
       ↓
Pago confirmado → Auditoría (runner.py)
       ↓
Informe entregado → Dashboard actualizado
```

## 6. Diferenciación Competitiva

| Factor | CodeAudit Pro | Competidores |
|--------|---------------|--------------|
| Precio | 299 € / 199 € mes | 1.000-10.000 € año |
| Entrega | 24h | 1-2 semanas |
| Formato | Informe HTML premium | RAW / PDF técnico |
| Sin instalación | ✅ Solo URL del repo | ❌ Agente en servidor |
| Modelo gratuito | ✅ OpenCode deepseek | ❌ Suscripciones caras |
| Enfocado PYME | ✅ Sí | ❌ Enterprise |

## 7. Checklist de Lanzamiento

- [ ] `prospect.py` funcional con mocks y API real.
- [ ] `landing/index.html` publicada en servidor.
- [ ] `payment.py` conectado a Stripe (modo test).
- [ ] `email_sender.py` configurado con Gmail SMTP.
- [ ] `dashboard/app.py` corriendo con autenticación.
- [ ] `runner.py` como servicio systemd o tarea cron.
- [ ] Repositorio GitHub público como muestra de trabajo.
- [ ] Perfil de LinkedIn actualizado.

---

> **Nota**: OpenCode con modelo deepseek-v4-flash-free es gratuito y no requiere API keys externas. El 100% del margen se queda en el negocio.

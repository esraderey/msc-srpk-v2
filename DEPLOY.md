# Guía de Despliegue Económico - MSC SRPK v2.0

## Análisis de lo que FALTA para producción

### Estado Actual del Proyecto
| Componente | Estado | Notas |
|---|---|---|
| Backend (FastAPI) | Funcional | 20+ endpoints, WebSocket |
| Landing Page | Mejorada | SEO, formulario de contacto, OG tags |
| Dashboard UI | Funcional | React via CDN |
| Billing UI | Funcional | Gestión de suscripciones |
| Monitoring UI | Funcional | Logs, alertas, métricas |
| Dockerfile | Funcional | Multi-stage build |
| K8s manifests | Funcional | Sobredimensionado para MVP |
| CI/CD (GitHub Actions) | Funcional | Tests, linting, seguridad |
| Sistema de billing | Funcional | SQLite, necesita Stripe real |
| Sistema de licencias | Funcional | Machine fingerprinting |

### Lo que se AGREGÓ en esta iteración
- `docker-compose.yml` - Orquestación completa para VPS
- `.env.example` - Todas las variables documentadas
- `nginx/` - Reverse proxy con SSL, rate limiting, security headers
- `web/static/robots.txt` - SEO
- `web/static/sitemap.xml` - SEO
- Landing page mejorada: OG tags, formulario de contacto, links corregidos

---

## Opción 1: VPS Económico ($5-10/mes) - RECOMENDADA para MVP

### Proveedores recomendados
| Proveedor | Plan | RAM | CPU | Disco | Precio |
|---|---|---|---|---|---|
| **Hetzner** | CX22 | 4GB | 2 vCPU | 40GB | ~$4.5/mes |
| **Contabo** | VPS S | 8GB | 4 vCPU | 200GB | ~$6.5/mes |
| DigitalOcean | Basic | 2GB | 1 vCPU | 50GB | $12/mes |
| Vultr | Regular | 2GB | 1 vCPU | 55GB | $10/mes |

### Pasos para desplegar

```bash
# 1. Conectar al VPS
ssh root@tu-ip

# 2. Instalar Docker
curl -fsSL https://get.docker.com | sh
apt install docker-compose-plugin -y

# 3. Clonar repositorio
git clone https://github.com/raulcruzacosta/msc-srpk.git
cd msc-srpk

# 4. Configurar variables
cp .env.example .env
nano .env  # Cambiar DOMAIN, claves de seguridad, etc.

# 5. Primer despliegue (sin SSL)
docker compose up -d

# 6. Verificar que funciona
curl http://localhost/api/status

# 7. Obtener certificado SSL (cambiar dominio y email)
docker compose run --rm certbot certonly --webroot \
  --webroot-path=/var/www/certbot \
  -d tu-dominio.com -d www.tu-dominio.com \
  --email tu@email.com --agree-tos

# 8. Activar HTTPS en nginx
# Descomentar el bloque HTTPS en nginx/conf.d/default.conf
# y comentar el bloque HTTP default_server
nano nginx/conf.d/default.conf

# 9. Reiniciar nginx
docker compose restart nginx
```

### Dominio (~$10/año)
- Namecheap, Cloudflare Registrar, o Porkbun
- Configurar DNS A record apuntando al IP del VPS

---

## Opción 2: Servicios Gratuitos/Freemium (costo $0-5/mes)

### Para landing page estática solamente:
- **GitHub Pages** (gratis) - Solo HTML estático
- **Cloudflare Pages** (gratis) - Build automático desde git
- **Netlify** (gratis) - Deploy automático, formularios incluidos

### Para backend + landing:
- **Railway.app** - $5/mes por hobby plan, deploy desde Docker
- **Render.com** - Free tier con limitaciones (sleep después de 15min)
- **Fly.io** - Free tier generoso, deploy Docker

### Limitaciones: PyTorch/transformers necesitan ~2GB RAM mínimo.
Los free tiers usualmente tienen 512MB. Necesitarás:
- Usar el fallback embedding model (sin CodeBERT real)
- O pagar por un plan con más RAM

---

## Opción 3: Cloud con Free Tier

### Google Cloud Run
```bash
# Build y push imagen
gcloud builds submit --tag gcr.io/PROJECT/msc-srpk
# Deploy
gcloud run deploy msc-srpk --image gcr.io/PROJECT/msc-srpk --port 8000
```
- Free tier: 2M requests/mes, 360K vCPU-seconds
- Escala a 0 cuando no hay tráfico

### AWS (más complejo pero económico con free tier)
- EC2 t2.micro (1 año gratis)
- Lightsail $3.50/mes

---

## Lo que TODAVÍA falta por implementar (priorizado)

### Prioridad ALTA (necesario para lanzar)
1. **Endpoint `/api/trial-request`** - Recibir solicitudes del formulario de la landing
   - Guardar en SQLite
   - Enviar email de confirmación (o log para procesar manualmente)

2. **CORS restringido** - Cambiar `allow_origins=["*"]` por dominios específicos en `web/backend/main.py:50`

3. **Secrets seguros** - Las variables `MSC_SRPK_MASTER_KEY` y `JWT_SECRET_KEY` en `.env` deben ser aleatorias y seguras

4. **Dominio + DNS** - Comprar dominio y apuntar al VPS

### Prioridad MEDIA (primera semana post-lanzamiento)
5. **Email transaccional** - Para enviar licencias de trial
   - Opciones económicas: Resend.com (gratis 100/día), Brevo (gratis 300/día)

6. **Stripe integración real** - El código de billing existe pero no conecta a Stripe real
   - `msc_srpk/billing.py` tiene la estructura, falta el webhook real

7. **Backup automático de SQLite** - Script cron para copiar las .db a un bucket o disco externo
   ```bash
   # Agregar al crontab del VPS
   0 3 * * * tar czf /backup/msc-srpk-$(date +%Y%m%d).tar.gz /app/data/*.db
   ```

8. **Métricas de error con Sentry** - Ya integrado en código, solo falta configurar `SENTRY_DSN` en `.env`

### Prioridad BAJA (cuando haya tracción)
9. **Migración de SQLite a PostgreSQL** - SQLite funciona bien para <1000 usuarios
10. **CDN para assets** - Cloudflare gratis frente al VPS
11. **Analytics** - Google Analytics o Plausible (más privado)
12. **A/B testing en landing** - Una vez haya tráfico suficiente
13. **Kubernetes** - Los manifests ya existen en `k8s/`, usar cuando el VPS se quede corto
14. **Load testing** - Scripts con locust o k6

---

## Resumen de Costos Mínimos para Lanzar

| Concepto | Costo | Notas |
|---|---|---|
| VPS (Hetzner CX22) | ~$4.5/mes | 4GB RAM, suficiente para todo |
| Dominio | ~$10/año | Namecheap o Cloudflare |
| SSL | $0 | Let's Encrypt (ya configurado) |
| Email transaccional | $0 | Resend/Brevo free tier |
| Monitoring (Sentry) | $0 | Free tier (5K events/mes) |
| **TOTAL** | **~$5.5/mes** | |

---

## Comandos Rápidos

```bash
# Desplegar todo
docker compose up -d

# Ver logs
docker compose logs -f web

# Actualizar código
git pull && docker compose up -d --build

# Backup manual
docker compose exec web tar czf /tmp/backup.tar.gz /app/data/
docker compose cp web:/tmp/backup.tar.gz ./backup.tar.gz

# Estado de servicios
docker compose ps

# Reiniciar solo un servicio
docker compose restart web
```

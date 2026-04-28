# ✅ Checklist de Configuración - VideoContextBot

## Antes de ejecutar `docker-compose up --build`

### 1. Configurar variables de entorno obligatorias

Edita el archivo `.env` y configura:

- [ ] **OPENAI_API_KEY**
  - Obtén tu API key en: https://platform.openai.com/api-keys
  - Formato: `sk-...`
  - Necesitas créditos en tu cuenta de OpenAI

- [ ] **TELEGRAM_BOT_TOKEN**
  - Token provisto: `8538919406:AAGROZELCgHKOhi-nPPt9phpfsht_QkwRro`
  - ✅ Ya está configurado en el `.env`

- [ ] **ALLOWED_USER_IDS** ⚠️ **CRÍTICO PARA SEGURIDAD**
  - Abre Telegram y busca `@userinfobot`
  - Inicia el bot y te mostrará tu ID numérico
  - Agrega tu ID al `.env`: `ALLOWED_USER_IDS=123456789`
  - Sin esto, el bot podría ser público (dependiendo de la configuración)

### 2. Verificar puertos disponibles

- [ ] Puerto 8000 (API) - disponible
- [ ] Puerto 7860 (Gradio) - disponible

Si están ocupados, edita `.env` y cambia:
```env
API_PORT=8001
GRADIO_PORT=7861
```

### 3. Verificar Docker

```bash
docker --version
docker-compose --version
```

Deberías tener Docker 20+ y Docker Compose 2+

### 4. Espacio en disco

El procesamiento de videos requiere espacio temporal:
- [ ] Al menos 10GB libres para videos de hasta 2GB

```bash
df -h
```

### 5. Construir y levantar

```bash
docker-compose up --build
```

### 6. Verificar servicios

En otra terminal:

```bash
docker-compose ps
```

Deberías ver 5 servicios:
- vcb_redis
- vcb_api
- vcb_celery_worker
- vcb_celery_beat
- vcb_telegram_bot
- vcb_gradio

### 7. Probar endpoints

- [ ] API Health: http://localhost:8000/health
- [ ] API Docs: http://localhost:8000/docs
- [ ] Web Gradio: http://localhost:7860

### 8. Probar bot de Telegram

- [ ] Busca tu bot en Telegram (usa el token configurado)
- [ ] Envía `/start`
- [ ] Debería responderte (si tu user_id está en ALLOWED_USER_IDS)

---

## 🐛 Problemas Comunes

### "No module named 'app.xxx'"
Rebuild: `docker-compose up --build --force-recreate`

### "Redis connection refused"
Espera a que Redis esté healthy: `docker-compose logs redis`

### "OpenAI API key invalid"
Verifica que `OPENAI_API_KEY` en `.env` sea correcto

### Bot no responde
1. Verifica `TELEGRAM_BOT_TOKEN`
2. Verifica `ALLOWED_USER_IDS` tiene tu user ID
3. Revisa logs: `docker-compose logs telegram-bot`

### Videos fallan al procesar
1. Verifica logs del worker: `docker-compose logs celery-worker`
2. Checkea que ffmpeg esté instalado: `docker-compose exec api ffmpeg -version`

---

## 📝 Comandos Útiles

```bash
# Ver logs en tiempo real
docker-compose logs -f

# Ver logs de un servicio específico
docker-compose logs -f celery-worker

# Reiniciar un servicio
docker-compose restart api

# Detener todo
docker-compose down

# Detener y limpiar volúmenes (¡cuidado! borra datos)
docker-compose down -v

# Ver jobs en la DB
docker-compose exec api python -c "
from app.database import SessionLocal
from app.models import Job
db = SessionLocal()
for job in db.query(Job).order_by(Job.created_at.desc()).limit(5).all():
    print(f'{job.job_id[:8]} - {job.status.value} - {job.progress}%')
"
```

---

## 🔒 Seguridad

### Bot de Telegram
- ✅ Protegido por `ALLOWED_USER_IDS`
- ⚠️ Configura tu user ID antes de exponer el bot

### API
- 🔓 Abierta por defecto (para desarrollo)
- 🔒 Para producción, configura `API_KEY` en `.env`

### Web (Gradio)
- 🔓 Abierta por defecto
- ⚠️ Si expones a internet, usa reverse proxy con auth

---

## 📊 Monitoreo

### Ver uso de recursos
```bash
docker stats
```

### Ver cola de Celery
```bash
docker-compose exec redis redis-cli
> llen celery
```

### Ver jobs activos
```bash
docker-compose logs -f celery-worker | grep "Task received"
```

---

## ✅ Listo para producción

Antes de desplegar en producción:

- [ ] Configura `API_KEY` en `.env`
- [ ] Usa HTTPS con reverse proxy (nginx/traefik)
- [ ] Configura límites de rate limiting
- [ ] Ajusta `CELERY_CONCURRENCY` según RAM disponible
- [ ] Configura logs persistentes
- [ ] Agrega backup para la DB SQLite
- [ ] Considera migrar a PostgreSQL para producción

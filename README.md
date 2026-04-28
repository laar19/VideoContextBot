# VideoContextBot

Procesamiento de videos de grabaciones de pantalla para generación de contexto rico para agentes de IA.

## 🎯 Características

- **Detección automática de audio**: Procesa videos con o sin pista de audio
- **Extracción inteligente de frames**: Usa PySceneDetect para capturar momentos clave
- **Transcripción con Whisper API**: Transcripción precisa con timestamps
- **PDF profesional**: Reporte estructurado con frames y transcripción
- **Múltiples interfaces**: API REST, Bot de Telegram, Web con Gradio
- **Procesamiento asíncrono**: Celery + Redis para videos grandes (hasta 2GB)

## 📋 Requisitos

- Docker y Docker Compose
- API Key de servicio compatible con OpenAI (Groq, OpenAI, DeepSeek, etc.)
- Token de Telegram Bot (opcional, solo si usas el bot)

## 🚀 Instalación y Configuración

### 1. Clonar y configurar variables de entorno

```bash
# Copiar archivo de ejemplo
cp .env.example .env

# Editar .env con tus credenciales
nano .env
```

### 2. Configurar variables obligatorias

```env
# API compatible con OpenAI (Groq recomendado - gratis y rápido)
OPENAI_API_KEY=tu-api-key

# Para Groq (recomendado):
OPENAI_BASE_URL=https://api.groq.com/openai/v1
WHISPER_MODEL=whisper-large-v3

# Para OpenAI oficial (alternativa):
# OPENAI_BASE_URL=
# WHISPER_MODEL=whisper-1

# Telegram Bot Token (si usas el bot)
TELEGRAM_BOT_TOKEN=8538919406:AAGROZELCgHKOhi-nPPt9phpfsht_QkwRro

# IDs de usuarios autorizados (OBLIGATORIO para seguridad)
# Obtén tu user ID con @userinfobot en Telegram
ALLOWED_USER_IDS=123456789
```

### 3. Obtener tu Telegram User ID

Para seguridad del bot, debes agregar tu user ID:

1. Abre Telegram y busca `@userinfobot`
2. Inicia el bot y te mostrará tu ID numérico
3. Agrega ese ID a `ALLOWED_USER_IDS` en el `.env`

### 4. Construir y levantar contenedores

```bash
docker-compose up --build
```

### 5. Verificar servicios

```bash
docker-compose ps
```

Deberías ver 5 servicios corriendo:
- `vcb_redis`
- `vcb_api` (puerto 8000)
- `vcb_celery_worker`
- `vcb_telegram_bot`
- `vcb_gradio` (puerto 7860)

## 📱 Uso

### Interfaz Web (Gradio)

Accede a: `http://localhost:7860`

1. Arrastra y suelta tu video
2. (Opcional) Agrega notas en el textarea o sube un .txt
3. Click en "Procesar Video"
4. Espera a que termine el procesamiento
5. Descarga el PDF y/o ZIP completo

### Bot de Telegram

1. Inicia una conversación con tu bot
2. Envía un video (como video o documento)
3. El bot detectará si tiene audio y te lo informará
4. (Opcional) Envía notas adicionales o un archivo .txt
5. El bot procesará en background y te enviará:
   - 📄 PDF con el reporte completo
   - 📦 ZIP con toda la carpeta de output

**Comandos del bot:**
- `/start` - Iniciar
- `/ayuda` - Guía de uso
- `/estado` - Ver jobs en progreso
- `/cancelar` - Cancelar job actual

### API REST

**Crear job:**
```bash
curl -X POST http://localhost:8000/api/jobs \
  -F "video=@/ruta/a/tu/video.mp4" \
  -F "notes=Notas adicionales opcionales"
```

**Ver estado:**
```bash
curl http://localhost:8000/api/jobs/{job_id}
```

**Descargar PDF:**
```bash
curl -O http://localhost:8000/api/jobs/{job_id}/pdf
```

**Descargar ZIP:**
```bash
curl -O http://localhost:8000/api/jobs/{job_id}/zip
```

**Documentación interactiva:** `http://localhost:8000/docs`

## 📁 Estructura del Proyecto

```
VideoContextBot/
├── app/
│   ├── main.py              # FastAPI app
│   ├── config.py            # Configuración
│   ├── database.py          # SQLite setup
│   ├── models.py            # Modelos DB
│   ├── celery_app.py        # Celery config
│   ├── tasks.py             # Tareas Celery
│   ├── processor/
│   │   ├── core.py          # Orquestador
│   │   ├── video_utils.py   # Video processing
│   │   ├── transcription.py # Whisper API
│   │   ├── pdf_generator.py # Generación PDF
│   │   └── utils.py         # Helpers
│   ├── telegram_bot/
│   │   └── bot.py           # Bot de Telegram
│   └── web/
│       └── gradio_app.py    # Interfaz Gradio
├── output/                  # Resultados (persistente)
├── temp/                    # Temporal (auto-limpieza)
├── logs/                    # Logs de la aplicación
├── db/                      # SQLite database
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── .env.example
└── README.md
```

## 🔧 Configuración Avanzada

### Variables de Entorno

| Variable | Descripción | Default |
|----------|-------------|---------|
| `OPENAI_API_KEY` | API Key de OpenAI | - |
| `TELEGRAM_BOT_TOKEN` | Token del bot | - |
| `ALLOWED_USER_IDS` | IDs autorizados (separados por coma) | - |
| `MAX_VIDEO_SIZE_MB` | Tamaño máximo de video | 2048 |
| `SCENE_DETECT_THRESHOLD` | Threshold detección escenas | 30 |
| `CELERY_CONCURRENCY` | Workers concurrentes | 2 |
| `TEMP_CLEANUP_HOURS` | Limpieza temp (horas) | 24 |
| `OUTPUT_CLEANUP_HOURS` | Limpieza output (horas) | 48 |

### Ajustar detección de escenas

Para videos con muchos cambios visuales, aumenta el threshold:

```env
SCENE_DETECT_THRESHOLD=35
```

Para videos con cambios sutiles, disminuye:

```env
SCENE_DETECT_THRESHOLD=25
```

### Aumentar workers para más concurrencia

```env
CELERY_CONCURRENCY=4
```

### Cambiar proveedor de Whisper

**Groq (recomendado - gratis y rápido):**
```env
OPENAI_API_KEY=gsk_tu-key
OPENAI_BASE_URL=https://api.groq.com/openai/v1
WHISPER_MODEL=whisper-large-v3
```

**OpenAI oficial:**
```env
OPENAI_API_KEY=sk-tu-key
OPENAI_BASE_URL=
WHISPER_MODEL=whisper-1
```

**DeepSeek:**
```env
OPENAI_API_KEY=tu-key
OPENAI_BASE_URL=https://api.deepseek.com/v1
WHISPER_MODEL=deepseek-whisper
```

**Ollama local:**
```env
OPENAI_API_KEY=ollama
OPENAI_BASE_URL=http://host.docker.internal:11434/v1
WHISPER_MODEL=whisper:large
```

## 🔒 Seguridad

### Bot de Telegram

El bot está protegido por whitelist de user IDs. Solo los IDs en `ALLOWED_USER_IDS` pueden usar el bot.

**Importante:** Configura `ALLOWED_USER_IDS` antes de exponer el bot.

### Interfaz Web

La interfaz Gradio es abierta (sin autenticación). Si la expones a internet:
- Usa un reverse proxy con autenticación
- O implementa auth básica en el docker-compose

### API

La API no tiene autenticación por defecto. Para producción:
- Agrega API key authentication
- Usa HTTPS con reverse proxy

## 🐛 Troubleshooting

### El bot no responde

1. Verifica que `TELEGRAM_BOT_TOKEN` sea correcto
2. Revisa logs: `docker-compose logs telegram-bot`
3. Asegúrate de que `ALLOWED_USER_IDS` tenga tu user ID

### Error "API key invalid"

1. Verifica que `OPENAI_API_KEY` en `.env` sea correcto
2. Verifica que `OPENAI_BASE_URL` sea correcto para tu proveedor
3. Revisa logs del worker: `docker-compose logs celery-worker`

### Videos muy grandes fallan

1. Aumenta timeout en `app/celery_app.py`:
   ```python
   task_time_limit=7200  # 2 horas
   ```
2. Reduce concurrencia para más memoria por worker

### Redis connection error

```bash
docker-compose restart redis
docker-compose logs redis
```

## 📊 Monitoreo

### Ver logs de todos los servicios

```bash
docker-compose logs -f
```

### Ver logs de un servicio específico

```bash
docker-compose logs -f celery-worker
```

### Ver jobs en la base de datos

```bash
docker-compose exec api python -c "
from app.database import SessionLocal
from app.models import Job
db = SessionLocal()
jobs = db.query(Job).order_by(Job.created_at.desc()).limit(10).all()
for job in jobs:
    print(f'{job.job_id[:8]} - {job.status.value} - {job.video_filename}')
"
```

## 🧹 Limpieza Manual

### Eliminar todos los jobs completados

```bash
docker-compose exec api python -c "
from app.database import SessionLocal
from app.models import Job, JobStatus
db = SessionLocal()
db.query(Job).filter(Job.status == JobStatus.COMPLETED).delete()
db.commit()
print('Jobs completados eliminados')
"
```

### Limpiar archivos antiguos

```bash
# Temp (más de 24h)
find ./temp -type d -mmin +1440 -exec rm -rf {} \;

# Output (más de 48h)
find ./output -type d -mmin +2880 -exec rm -rf {} \;
```

## 📝 Formatos Soportados

- **Video:** MP4, MKV, AVI, MOV, WebM
- **Audio:** Cualquier codec soportado por ffmpeg
- **Tamaño:** Hasta 2GB (configurable)

## 🔄 Flujo de Procesamiento

1. **Upload** → Usuario envía video
2. **Validate** → Verifica formato y tamaño
3. **Create Job** → SQLite: job_id, status="pending"
4. **Queue Task** → Celery encola procesamiento
5. **Process:**
   - Detectar audio (pymediainfo)
   - Extraer frames (PySceneDetect + OpenCV)
   - Transcribir si hay audio (Whisper API)
   - Generar PDF (fpdf2)
   - Crear ZIP
6. **Update Job** → status="completed"
7. **Deliver** → Entrega PDF + ZIP

## 🛠️ Desarrollo

### Correr localmente (sin Docker)

```bash
# Instalar dependencias
pip install -r requirements.txt

# Instalar ffmpeg
sudo apt install ffmpeg

# Configurar .env
cp .env.example .env
# Editar .env...

# Iniciar Redis
redis-server

# Iniciar API
python -m app.main

# Iniciar worker (otra terminal)
celery -A app.celery_app worker --loglevel=info

# Iniciar bot (otra terminal)
python -m app.telegram_bot.bot

# Iniciar Gradio (otra terminal)
python -m app.web.gradio_app
```

## 📄 Licencia

MIT

## 🤝 Soporte

Para issues o preguntas, abre un issue en el repositorio.

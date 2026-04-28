from celery import Celery
from app.config import settings

# Crear instancia de Celery
celery_app = Celery(
    "videocontextbot",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.tasks"]
)

# Configuración de Celery
celery_app.conf.update(
    # Timeouts para tareas largas (videos grandes)
    task_time_limit=3600,  # 1 hora máxima por tarea
    task_soft_time_limit=3300,  # 55 minutos soft limit
    
    # Reintentos
    task_autoretry_for=(Exception,),
    task_max_retries=2,
    task_default_retry_delay=60,
    
    # Serialización
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    
    # Timezone
    timezone="UTC",
    enable_utc=True,
    
    # Tracking de resultados
    result_extended=True,
    result_expires=3600,
    
    # Rate limiting
    worker_prefetch_multiplier=1,
    
    # Beat schedule para tareas periódicas
    beat_schedule={
        "cleanup-every-day": {
            "task": "app.tasks.cleanup_old_files_task",
            "schedule": 3600.0,  # Cada hora
        },
    },
)

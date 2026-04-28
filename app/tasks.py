from celery import Task
from app.celery_app import celery_app
from app.database import SessionLocal, engine, Base
from app.models import Job, JobStatus
from app.processor.core import process_video
from app.config import settings
from datetime import datetime
from pathlib import Path
import shutil


# Crear tablas si no existen
Base.metadata.create_all(bind=engine)


class VideoProcessingTask(Task):
    """Task base con configuración especial para procesamiento de video"""
    
    autoretry_for = (Exception,)
    max_retries = 2
    default_retry_delay = 60
    time_limit = 3600  # 1 hora
    soft_time_limit = 3300
    
    def on_success(self, retval, task_id, args, kwargs):
        """Callback cuando la tarea tiene éxito"""
        pass
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Callback cuando la tarea falla"""
        # Actualizar job en DB
        db = SessionLocal()
        try:
            job = db.query(Job).filter(Job.job_id == task_id).first()
            if job:
                job.status = JobStatus.FAILED
                job.error_message = str(exc)
                job.progress = 0
                job.completed_at = datetime.now()
                db.commit()
        finally:
            db.close()


@celery_app.task(
    base=VideoProcessingTask,
    bind=True,
    name="app.tasks.process_video_task"
)
def process_video_task(
    self,
    job_id: str,
    video_path: str,
    additional_notes: str = None
):
    """
    Tarea Celery para procesamiento de video en background
    """
    db = SessionLocal()
    job = None
    
    try:
        # Obtener job de DB
        job = db.query(Job).filter(Job.job_id == job_id).first()
        if not job:
            raise ValueError(f"Job {job_id} no encontrado")
        
        # Actualizar estado
        job.status = JobStatus.PROCESSING
        job.started_at = datetime.now()
        db.commit()
        
        def progress_callback(percent: int, message: str):
            """Actualizar progreso en DB"""
            job.progress = percent
            job.progress_message = message
            db.commit()
        
        # Ejecutar procesamiento
        result = process_video(
            video_path=video_path,
            job_id=job_id,
            additional_notes=additional_notes,
            progress_callback=progress_callback
        )
        
        # Actualizar job con resultados
        if result["success"]:
            job.status = JobStatus.COMPLETED
            job.has_audio = result["has_audio"]
            job.video_duration = result["video_info"].get("duration", "N/A")
            job.output_folder = result["output_folder"]
            job.transcription_path = result["transcription_path"]
            job.pdf_path = result["pdf_path"]
            job.zip_path = result["zip_path"]
            job.progress = 100
            job.progress_message = "Completado"
        else:
            job.status = JobStatus.FAILED
            job.error_message = result.get("error", "Error desconocido")
            job.progress = 0
        
        job.completed_at = datetime.now()
        db.commit()
        
        return result
        
    except Exception as e:
        # Manejar error
        if job:
            job.status = JobStatus.FAILED
            job.error_message = str(e)
            job.completed_at = datetime.now()
            db.commit()
        
        # Reintentar si es error temporal
        retry_exceptions = (ConnectionError, TimeoutError)
        if isinstance(e, retry_exceptions) and self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=60)
        
        raise


@celery_app.task(name="app.tasks.cleanup_old_files")
def cleanup_old_files_task():
    """Tarea periódica para limpiar archivos antiguos"""
    from app.processor.utils import cleanup_old_files
    
    try:
        cleanup_old_files()
        return {"success": True, "message": "Limpieza completada"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@celery_app.task(name="app.tasks.delete_job_files")
def delete_job_files_task(job_id: str):
    """Eliminar archivos de un job específico"""
    db = SessionLocal()
    
    try:
        job = db.query(Job).filter(Job.job_id == job_id).first()
        if not job:
            return {"success": False, "error": "Job no encontrado"}
        
        # Eliminar carpeta de output
        if job.output_folder:
            output_path = Path(job.output_folder)
            if output_path.exists():
                shutil.rmtree(output_path)
        
        # Eliminar ZIP si existe separado
        if job.zip_path:
            zip_path = Path(job.zip_path)
            if zip_path.exists():
                zip_path.unlink()
        
        # Actualizar job
        job.status = JobStatus.CANCELLED
        db.commit()
        
        return {"success": True}
        
    except Exception as e:
        return {"success": False, "error": str(e)}
    
    finally:
        db.close()

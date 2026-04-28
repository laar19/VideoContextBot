from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime
import uuid
import shutil
from pathlib import Path

from app.database import get_db, init_db
from app.models import Job, JobStatus
from app.config import settings
from app.tasks import process_video_task, delete_job_files_task
from app.processor.utils import validate_video_file, create_temp_folder, generate_job_id

# Inicializar DB
init_db()

# Security scheme (opcional)
security = HTTPBearer(auto_error=False)

# Crear app FastAPI
app = FastAPI(
    title="VideoContextBot API",
    description="API para procesamiento de videos y generación de contexto",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def verify_api_key(request: Request, credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)):
    """Verificar API key si está configurada"""
    # Si no hay API_KEY configurada, permitir todo
    api_key = getattr(settings, 'API_KEY', None)
    if not api_key:
        return None
    
    # Si hay API_KEY, verificar credenciales
    if not credentials:
        raise HTTPException(status_code=401, detail="API key requerida")
    
    if credentials.credentials != api_key:
        raise HTTPException(status_code=401, detail="API key inválida")
    
    return credentials.credentials


@app.get("/health")
async def health_check():
    """Endpoint de health check"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": settings.SERVICE_NAME
    }


@app.post("/api/jobs", status_code=201)
async def create_job(
    video: UploadFile = File(..., description="Archivo de video"),
    notes: Optional[str] = Form(None, description="Notas adicionales"),
    db: Session = Depends(get_db)
):
    """
    Crear nuevo job de procesamiento de video
    
    - Sube un video
    - Opcionalmente añade notas
    - Retorna job_id para trackear progreso
    """
    # Validar archivo
    if not video.filename:
        raise HTTPException(status_code=400, detail="Nombre de archivo requerido")
    
    # Validar tamaño
    content = await video.read()
    video_size = len(content)
    max_size = settings.max_video_size_bytes
    
    if video_size > max_size:
        raise HTTPException(
            status_code=413,
            detail=f"Archivo muy grande: {video_size / 1024 / 1024:.1f}MB. Máximo: {settings.MAX_VIDEO_SIZE_MB}MB"
        )
    
    # Validar formato
    temp_video = settings.TEMP_DIR / f"temp_{video.filename}"
    with open(temp_video, "wb") as f:
        f.write(content)
    
    is_valid, error_msg = validate_video_file(str(temp_video))
    if not is_valid:
        temp_video.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=error_msg)
    
    # Crear job en DB
    job_id = generate_job_id()
    job = Job(
        job_id=job_id,
        status=JobStatus.PENDING,
        video_path=str(temp_video),
        video_filename=video.filename,
        additional_notes=notes,
        source="api",
        progress=0,
        progress_message="Esperando procesamiento..."
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    
    # Encolar tarea Celery
    process_video_task.delay(
        job_id=job_id,
        video_path=str(temp_video),
        additional_notes=notes
    )
    
    return {
        "job_id": job_id,
        "status": job.status.value,
        "message": "Job creado exitosamente. Usa GET /api/jobs/{job_id} para ver progreso."
    }


@app.get("/api/jobs")
async def list_jobs(
    status: Optional[str] = None,
    limit: int = 20,
    db: Session = Depends(get_db)
):
    """Listar jobs con filtro opcional por estado"""
    query = db.query(Job)
    
    if status:
        try:
            status_enum = JobStatus(status)
            query = query.filter(Job.status == status_enum)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Estado inválido. Válidos: {[s.value for s in JobStatus]}"
            )
    
    jobs = query.order_by(Job.created_at.desc()).limit(limit).all()
    
    return {
        "jobs": [
            {
                "job_id": job.job_id,
                "status": job.status.value,
                "filename": job.video_filename,
                "has_audio": job.has_audio,
                "progress": job.progress,
                "progress_message": job.progress_message,
                "created_at": job.created_at.isoformat(),
                "completed_at": job.completed_at.isoformat() if job.completed_at else None
            }
            for job in jobs
        ]
    }


@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str, db: Session = Depends(get_db)):
    """Obtener estado de un job específico"""
    job = db.query(Job).filter(Job.job_id == job_id).first()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job no encontrado")
    
    return {
        "job_id": job.job_id,
        "status": job.status.value,
        "filename": job.video_filename,
        "has_audio": job.has_audio,
        "video_duration": job.video_duration,
        "progress": job.progress,
        "progress_message": job.progress_message,
        "error_message": job.error_message,
        "created_at": job.created_at.isoformat(),
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "output_folder": job.output_folder,
        "pdf_path": job.pdf_path,
        "zip_path": job.zip_path
    }


@app.get("/api/jobs/{job_id}/pdf")
async def download_pdf(job_id: str, db: Session = Depends(get_db)):
    """Descargar PDF del job"""
    job = db.query(Job).filter(Job.job_id == job_id).first()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job no encontrado")
    
    if job.status != JobStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail=f"Job no completado. Estado: {job.status.value}"
        )
    
    if not job.pdf_path:
        raise HTTPException(status_code=404, detail="PDF no encontrado")
    
    pdf_path = Path(job.pdf_path)
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="Archivo PDF no existe")
    
    return FileResponse(
        path=str(pdf_path),
        media_type="application/pdf",
        filename=f"{job.video_filename.rsplit('.', 1)[0]}_report.pdf"
    )


@app.get("/api/jobs/{job_id}/zip")
async def download_zip(job_id: str, db: Session = Depends(get_db)):
    """Descargar ZIP completo del job"""
    job = db.query(Job).filter(Job.job_id == job_id).first()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job no encontrado")
    
    if job.status != JobStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail=f"Job no completado. Estado: {job.status.value}"
        )
    
    if not job.zip_path:
        raise HTTPException(status_code=404, detail="ZIP no encontrado")
    
    zip_path = Path(job.zip_path)
    if not zip_path.exists():
        raise HTTPException(status_code=404, detail="Archivo ZIP no existe")
    
    return FileResponse(
        path=str(zip_path),
        media_type="application/zip",
        filename=f"{job.video_filename.rsplit('.', 1)[0]}_output.zip"
    )


@app.delete("/api/jobs/{job_id}")
async def delete_job(job_id: str, db: Session = Depends(get_db)):
    """Eliminar job y sus archivos"""
    job = db.query(Job).filter(Job.job_id == job_id).first()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job no encontrado")
    
    # Encolar tarea de limpieza
    delete_job_files_task.delay(job_id=job_id)
    
    return {"message": "Job eliminado. Archivos en proceso de limpieza."}


@app.get("/api/info")
async def api_info():
    """Información de la API"""
    return {
        "name": "VideoContextBot API",
        "version": "1.0.0",
        "description": "Procesamiento de videos para generación de contexto",
        "features": [
            "Detección automática de audio",
            "Extracción inteligente de frames",
            "Transcripción con Whisper API",
            "Generación de PDF profesional",
            "Descarga de output completo en ZIP"
        ],
        "max_video_size_mb": settings.MAX_VIDEO_SIZE_MB,
        "supported_formats": [".mp4", ".mkv", ".avi", ".mov", ".webm"]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=settings.API_PORT)

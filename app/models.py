from sqlalchemy import Column, Integer, String, DateTime, Enum, Text, Boolean
from sqlalchemy.sql import func
import enum
from app.database import Base


class JobStatus(str, enum.Enum):
    """Estados posibles de un job de procesamiento"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Job(Base):
    """Modelo para tracking de jobs de procesamiento"""
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    
    # Identificador único del job (UUID)
    job_id = Column(String(36), unique=True, index=True, nullable=False)
    
    # Estado actual
    status = Column(Enum(JobStatus), default=JobStatus.PENDING, nullable=False)
    
    # Paths de archivos
    video_path = Column(String, nullable=False)
    video_filename = Column(String, nullable=False)
    output_folder = Column(String, nullable=True)
    
    # Información del video
    has_audio = Column(Boolean, nullable=True)
    video_duration = Column(String, nullable=True)
    
    # Transcripción
    transcription_path = Column(String, nullable=True)
    
    # PDF y ZIP
    pdf_path = Column(String, nullable=True)
    zip_path = Column(String, nullable=True)
    
    # Notas adicionales
    additional_notes = Column(Text, nullable=True)
    
    # Mensaje de error si falla
    error_message = Column(Text, nullable=True)
    
    # Progreso (0-100)
    progress = Column(Integer, default=0)
    progress_message = Column(String, default="Iniciando...")
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Metadata extra
    user_id = Column(String, nullable=True)  # ID de Telegram o "web"
    source = Column(String, default="api")  # "telegram", "web", "api"

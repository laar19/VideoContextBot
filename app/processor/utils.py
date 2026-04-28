import uuid
import os
import shutil
from pathlib import Path
from datetime import datetime
import zipfile
from app.config import settings


def generate_job_id() -> str:
    """Generar ID único para job"""
    return str(uuid.uuid4())


def create_output_folder(job_id: str) -> Path:
    """Crear carpeta de output para un job"""
    output_path = settings.OUTPUT_DIR / f"output_{job_id[:8]}"
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Crear subcarpeta para capturas
    captures_path = output_path / "captures"
    captures_path.mkdir(exist_ok=True)
    
    return output_path


def create_temp_folder(job_id: str) -> Path:
    """Crear carpeta temporal para un job"""
    temp_path = settings.TEMP_DIR / f"temp_{job_id[:8]}"
    temp_path.mkdir(parents=True, exist_ok=True)
    return temp_path


def cleanup_temp_folder(job_id: str):
    """Eliminar carpeta temporal"""
    temp_path = settings.TEMP_DIR / f"temp_{job_id[:8]}"
    if temp_path.exists():
        shutil.rmtree(temp_path)


def format_timestamp(seconds: float) -> str:
    """Formatear segundos a formato MM:SS o HH:MM:SS"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def format_timestamp_for_filename(seconds: float) -> str:
    """Formatear timestamp para nombre de archivo"""
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes:02d}m{secs:02d}s"


def create_zip_folder(output_folder: Path) -> Path:
    """Crear archivo ZIP con todo el contenido de la carpeta de output"""
    zip_path = output_folder.parent / f"{output_folder.name}.zip"
    
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(output_folder):
            for file in files:
                file_path = Path(root) / file
                arcname = file_path.relative_to(output_folder.parent)
                zipf.write(file_path, arcname)
    
    return zip_path


def get_file_size_mb(file_path: str) -> float:
    """Obtener tamaño de archivo en MB"""
    return os.path.getsize(file_path) / (1024 * 1024)


def validate_video_file(file_path: str) -> tuple[bool, str]:
    """Validar archivo de video"""
    path = Path(file_path)
    
    # Verificar extensión
    valid_extensions = {'.mp4', '.mkv', '.avi', '.mov', '.webm'}
    if path.suffix.lower() not in valid_extensions:
        return False, f"Extensión no soportada: {path.suffix}. Formatos válidos: {', '.join(valid_extensions)}"
    
    # Verificar tamaño
    size_mb = get_file_size_mb(file_path)
    if size_mb > settings.MAX_VIDEO_SIZE_MB:
        return False, f"Archivo muy grande: {size_mb:.1f}MB. Máximo: {settings.MAX_VIDEO_SIZE_MB}MB"
    
    return True, "OK"


def cleanup_old_files():
    """Limpiar archivos antiguos de temp y output"""
    from datetime import timedelta
    
    now = datetime.now()
    
    # Limpiar temp
    if settings.TEMP_DIR.exists():
        for item in settings.TEMP_DIR.iterdir():
            if item.is_dir():
                try:
                    mtime = datetime.fromtimestamp(item.stat().st_mtime)
                    age = now - mtime
                    if age > timedelta(hours=settings.TEMP_CLEANUP_HOURS):
                        shutil.rmtree(item)
                except Exception:
                    pass
    
    # Limpiar output (más conservador)
    if settings.OUTPUT_DIR.exists():
        for item in settings.OUTPUT_DIR.iterdir():
            if item.is_dir():
                try:
                    mtime = datetime.fromtimestamp(item.stat().st_mtime)
                    age = now - mtime
                    if age > timedelta(hours=settings.OUTPUT_CLEANUP_HOURS):
                        shutil.rmtree(item)
                except Exception:
                    pass

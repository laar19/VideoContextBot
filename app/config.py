import os
from typing import Optional
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Configuración centralizada de la aplicación"""

    # OpenAI-compatible API (OpenAI, Groq, DeepSeek, etc.)
    OPENAI_API_KEY: str = Field(..., description="API Key para servicio compatible con OpenAI")
    OPENAI_BASE_URL: Optional[str] = Field(
        default=None,
        description="Base URL del API (None para OpenAI oficial, ej: https://api.groq.com/openai/v1 para Groq)"
    )
    WHISPER_MODEL: str = Field(
        default="whisper-large-v3",
        description="Modelo Whisper a usar (whisper-1 para OpenAI, whisper-large-v3 para Groq)"
    )
    
    # API Security (opcional)
    API_KEY: Optional[str] = Field(None, description="API Key para proteger endpoints")

    # Telegram
    TELEGRAM_BOT_TOKEN: str = Field(..., description="Token del bot de Telegram")
    ALLOWED_USER_IDS: str = Field(
        default="",
        description="IDs de usuarios autorizados separados por comas"
    )

    # Redis
    REDIS_URL: str = Field(default="redis://redis:6379/0")

    # Database
    DATABASE_URL: str = Field(default="sqlite:///./db/videocontextbot.db")

    # Server
    API_PORT: int = Field(default=8000)
    GRADIO_PORT: int = Field(default=7860)

    # Video Processing
    MAX_VIDEO_SIZE_MB: int = Field(default=2048, description="Tamaño máximo de video en MB")
    SCENE_DETECT_THRESHOLD: float = Field(default=30.0, description="Threshold para detección de escenas")
    CELERY_CONCURRENCY: int = Field(default=2, description="Workers Celery concurrentes")

    # Directories
    OUTPUT_DIR: Path = Field(default=Path("/app/output"))
    TEMP_DIR: Path = Field(default=Path("/app/temp"))
    LOGS_DIR: Path = Field(default=Path("/app/logs"))

    # Cleanup
    TEMP_CLEANUP_HOURS: int = Field(default=24)
    OUTPUT_CLEANUP_HOURS: int = Field(default=48)

    # Logging
    LOG_LEVEL: str = Field(default="INFO")

    # Service name (para identificar el contenedor)
    SERVICE_NAME: str = Field(default="api")

    @property
    def allowed_user_ids(self) -> set[int]:
        """Retorna set de IDs de usuarios autorizados"""
        if not self.ALLOWED_USER_IDS:
            return set()
        try:
            return {int(id.strip()) for id in self.ALLOWED_USER_IDS.split(",") if id.strip()}
        except ValueError:
            return set()

    @property
    def max_video_size_bytes(self) -> int:
        """Retorna tamaño máximo en bytes"""
        return self.MAX_VIDEO_SIZE_MB * 1024 * 1024

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


# Instancia global de settings
settings = Settings()

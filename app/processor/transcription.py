from openai import OpenAI
from typing import Optional
from app.config import settings
from app.processor.utils import format_timestamp


def get_openai_client() -> OpenAI:
    """
    Crear cliente OpenAI compatible con cualquier proveedor
    
    Soporta:
    - OpenAI oficial (sin base_url)
    - Groq (https://api.groq.com/openai/v1)
    - DeepSeek, Ollama, u otros compatibles
    """
    return OpenAI(
        api_key=settings.OPENAI_API_KEY,
        base_url=settings.OPENAI_BASE_URL
    )


def transcribe_audio(
    video_path: str,
    progress_callback: Optional[callable] = None
) -> dict:
    """
    Transcribir audio del video usando API compatible con OpenAI
    
    Returns: dict con {
        'text': str,
        'segments': list[{'start': float, 'end': float, 'text': str}],
        'language': str
    }
    """
    client = get_openai_client()
    
    try:
        if progress_callback:
            progress_callback(5, f"Enviando audio a {settings.OPENAI_BASE_URL or 'OpenAI'}...")
        
        with open(video_path, "rb") as audio_file:
            response = client.audio.transcriptions.create(
                model=settings.WHISPER_MODEL,
                file=audio_file,
                response_format="verbose_json",
                timestamp_granularities=["segment"]
            )
        
        if progress_callback:
            progress_callback(15, "Procesando transcripción...")
        
        # Extraer información de la respuesta
        result = {
            "text": response.text,
            "language": getattr(response, "language", "unknown"),
            "segments": []
        }
        
        # Procesar segmentos con timestamps
        if hasattr(response, "segments"):
            for segment in response.segments:
                # Los segmentos pueden ser objetos o dicts
                result["segments"].append({
                    "start": float(segment.start if hasattr(segment, 'start') else segment.get("start", 0)),
                    "end": float(segment.end if hasattr(segment, 'end') else segment.get("end", 0)),
                    "text": segment.text if hasattr(segment, 'text') else segment.get("text", "")
                })
        
        return result
        
    except Exception as e:
        print(f"Error en transcripción Whisper: {e}")
        raise


def format_transcription_for_txt(transcription_result: dict) -> str:
    """Formatear transcripción para archivo de texto"""
    lines = []
    
    # Header con idioma detectado
    language = transcription_result.get("language", "desconocido")
    lines.append(f"=== TRANSCRIPCIÓN ===")
    lines.append(f"Idioma detectado: {language}")
    lines.append("")
    
    # Segmentos con timestamps
    segments = transcription_result.get("segments", [])
    for segment in segments:
        start = format_timestamp(segment["start"])
        end = format_timestamp(segment["end"])
        text = segment["text"].strip()
        lines.append(f"[{start} - {end}] {text}")
    
    # Texto completo al final
    lines.append("")
    lines.append("=== TEXTO COMPLETO ===")
    lines.append(transcription_result.get("text", ""))
    
    return "\n".join(lines)


def get_segments_for_timestamp(
    transcription_result: dict,
    timestamp: float,
    window_seconds: float = 15.0
) -> list[str]:
    """
    Obtener segmentos de transcripción relevantes para un timestamp
    
    window_seconds: Ventana de tiempo alrededor del timestamp (±window_seconds/2)
    """
    segments = transcription_result.get("segments", [])
    relevant = []
    
    window_half = window_seconds / 2
    start_time = timestamp - window_half
    end_time = timestamp + window_half
    
    for segment in segments:
        seg_start = segment["start"]
        seg_end = segment["end"]
        
        # Verificar si hay solapamiento
        if seg_start <= end_time and seg_end >= start_time:
            relevant.append(segment["text"].strip())
    
    return relevant

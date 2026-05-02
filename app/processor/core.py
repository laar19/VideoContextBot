import shutil
from pathlib import Path
from typing import Optional, Callable
from app.config import settings
from app.processor.video_utils import (
    has_audio_track,
    get_video_duration,
    extract_frames,
    get_video_info
)
from app.processor.transcription import (
    transcribe_audio,
    format_transcription_for_txt
)
from app.processor.pdf_generator import generate_pdf
from app.processor.utils import create_output_folder, create_zip_folder, cleanup_temp_folder


def process_video(
    video_path: str,
    job_id: str,
    additional_notes: Optional[str] = None,
    progress_callback: Optional[Callable[[int, str], None]] = None,
    frame_interval: Optional[int] = None
) -> dict:
    """
    Orquestador principal del procesamiento de video
    
    Args:
        video_path: Path al archivo de video
        job_id: ID único del job
        additional_notes: Notas adicionales opcionales
        progress_callback: Callback para reportar progreso (progress_percent, message)
        frame_interval: Intervalo en segundos entre capturas. None o 0 = Auto (scene detection)
    
    Returns: dict con resultados del procesamiento
    """
    result = {
        "job_id": job_id,
        "success": False,
        "has_audio": False,
        "video_info": {},
        "frames_extracted": 0,
        "transcription_segments": 0,
        "output_folder": None,
        "pdf_path": None,
        "zip_path": None,
        "transcription_path": None,
        "error": None
    }
    
    def report_progress(percent: int, message: str):
        if progress_callback:
            progress_callback(percent, message)
    
    try:
        # 1. Crear carpetas
        report_progress(0, "Preparando directorios...")
        output_folder = create_output_folder(job_id)
        result["output_folder"] = str(output_folder)
        
        # 2. Obtener información del video
        report_progress(2, "Analizando video...")
        video_info = get_video_info(video_path)
        result["video_info"] = video_info
        result["has_audio"] = video_info["has_audio"]
        
        # 3. Extraer frames
        report_progress(5, "Extrayendo frames...")
        frames_info = extract_frames(
            video_path,
            output_folder / "captures",
            interval_seconds=frame_interval
        )
        result["frames_extracted"] = len(frames_info)
        
        # 4. Transcribir audio (si existe)
        transcription_result = None
        if video_info["has_audio"]:
            report_progress(10, "Transcribiendo audio con Whisper...")
            try:
                transcription_result = transcribe_audio(
                    video_path,
                    progress_callback=lambda p, m: report_progress(10 + (p * 0.4), m)
                )
                result["transcription_segments"] = len(transcription_result.get("segments", []))
                
                # Guardar transcripción en archivo
                transcription_text = format_transcription_for_txt(transcription_result)
                transcription_path = output_folder / "transcription.txt"
                with open(transcription_path, "w", encoding="utf-8") as f:
                    f.write(transcription_text)
                result["transcription_path"] = str(transcription_path)
                
            except Exception as e:
                print(f"Error en transcripción: {e}")
                result["error"] = f"Error en transcripción: {str(e)}"
                # Continuar sin transcripción
                transcription_result = None
        else:
            # Crear archivo de transcripción vacío con nota
            transcription_path = output_folder / "transcription.txt"
            with open(transcription_path, "w", encoding="utf-8") as f:
                f.write("=== SIN AUDIO ===\n\n")
                f.write("Este video no contiene pista de audio.\n")
                f.write("Por lo tanto, no hay transcripción disponible.\n")
            result["transcription_path"] = str(transcription_path)
        
        report_progress(55, "Generando PDF...")
        
        # 5. Generar PDF
        duration_str = f"{video_info['duration']:.2f}s" if video_info.get('duration') else "Desconocida"
        pdf_path = generate_pdf(
            output_folder=output_folder,
            video_filename=video_info.get("filename", "unknown"),
            has_audio=video_info["has_audio"],
            duration=duration_str,
            frames_info=frames_info,
            transcription_result=transcription_result,
            additional_notes=additional_notes
        )
        result["pdf_path"] = pdf_path
        
        report_progress(85, "Creando archivo ZIP...")
        
        # 6. Crear ZIP
        zip_path = create_zip_folder(output_folder)
        result["zip_path"] = str(zip_path)
        
        report_progress(100, "Procesamiento completado!")
        
        result["success"] = True
        
    except Exception as e:
        print(f"Error en procesamiento: {e}")
        result["error"] = str(e)
        result["success"] = False
        
        # Cleanup en caso de error
        try:
            output_folder = settings.OUTPUT_DIR / f"output_{job_id[:8]}"
            if output_folder.exists():
                shutil.rmtree(output_folder)
        except Exception:
            pass
    
    finally:
        # Limpiar temp
        cleanup_temp_folder(job_id)
    
    return result

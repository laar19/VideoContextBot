import subprocess
import json
from pathlib import Path
from typing import Optional
from pymediainfo import MediaInfo
import cv2
from scenedetect import detect, ContentDetector
from app.config import settings
from app.processor.utils import format_timestamp_for_filename


def has_audio_track(video_path: str) -> bool:
    """Detectar si el video tiene pista de audio usando pymediainfo"""
    try:
        media_info = MediaInfo.parse(video_path)
        
        for track in media_info.tracks:
            if track.track_type == "Audio":
                return True
        
        return False
    except Exception as e:
        print(f"Error detectando audio: {e}")
        # Fallback: intentar con ffprobe
        return has_audio_ffprobe(video_path)


def has_audio_ffprobe(video_path: str) -> bool:
    """Fallback: detectar audio con ffprobe"""
    try:
        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_streams",
            video_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        data = json.loads(result.stdout)
        
        for stream in data.get("streams", []):
            if stream.get("codec_type") == "audio":
                return True
        
        return False
    except Exception as e:
        print(f"Error con ffprobe: {e}")
        return False


def get_video_duration(video_path: str) -> float:
    """Obtener duración del video en segundos"""
    try:
        media_info = MediaInfo.parse(video_path)
        duration = media_info.duration or 0
        return duration / 1000.0  # Convertir ms a segundos
    except Exception:
        return get_video_duration_ffprobe(video_path)


def get_video_duration_ffprobe(video_path: str) -> float:
    """Fallback: obtener duración con ffprobe"""
    try:
        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            video_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        data = json.loads(result.stdout)
        return float(data.get("format", {}).get("duration", 0))
    except Exception:
        return 0.0


def get_video_info(video_path: str) -> dict:
    """Obtener información completa del video"""
    return {
        "has_audio": has_audio_track(video_path),
        "duration": get_video_duration(video_path),
        "path": video_path,
        "filename": Path(video_path).name
    }


def extract_frames(
    video_path: str,
    output_dir: Path,
    threshold: Optional[float] = None,
    interval_seconds: Optional[int] = None
) -> list[dict]:
    """
    Extraer frames únicos detectando cambios de escena con PySceneDetect
    
    Args:
        video_path: Path al video
        output_dir: Directorio de salida
        threshold: Threshold para detección de escenas
        interval_seconds: Si > 0, usa extracción por intervalo en vez de scene detection.
                         None o 0 = Auto (scene detection con fallback por intervalo)
    
    Returns: Lista de dicts con {'frame_num', 'timestamp', 'path'}
    """
    if threshold is None:
        threshold = settings.SCENE_DETECT_THRESHOLD
    
    # Si se especificó intervalo, usar extracción por intervalo directamente
    if interval_seconds and interval_seconds > 0:
        frames_info = extract_frames_interval(
            video_path,
            output_dir,
            interval_seconds=interval_seconds
        )
        if len(frames_info) > settings.MAX_FRAME_COUNT:
            frames_info = subsample_frames(frames_info, settings.MAX_FRAME_COUNT)
        return frames_info[:settings.MAX_FRAME_COUNT]

    frames_info = []
    
    try:
        # Detectar escenas con ContentDetector
        scene_list = detect(
            video_path,
            ContentDetector(threshold=threshold),
            start_in_scene=True
        )
        
        # Abrir video con OpenCV
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        
        for idx, (start, end) in enumerate(scene_list):
            # Convertir FrameTimecode a segundos
            start_sec = start.get_seconds() if hasattr(start, 'get_seconds') else float(start)
            
            frame_num = int(start_sec * fps)
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
            ret, frame = cap.read()
            
            if ret:
                timestamp = start_sec
                timestamp_str = format_timestamp_for_filename(timestamp)
                
                frame_filename = f"frame_{idx + 1:03d}_{timestamp_str}.jpg"
                frame_path = output_dir / frame_filename
                
                # Redimensionar si es muy grande (max 1920px width)
                height, width = frame.shape[:2]
                if width > 1920:
                    scale = 1920 / width
                    new_width = int(width * scale)
                    new_height = int(height * scale)
                    frame = cv2.resize(frame, (new_width, new_height))
                
                cv2.imwrite(str(frame_path), frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                
                frames_info.append({
                    "frame_num": idx + 1,
                    "timestamp": timestamp,
                    "path": str(frame_path),
                    "filename": frame_filename
                })
        
        cap.release()
        
        # Si hay muy pocos frames, agregar por intervalo
        if len(frames_info) < settings.MIN_FRAME_COUNT:
            additional = extract_frames_interval(
                video_path, 
                output_dir, 
                interval_seconds=settings.FRAME_INTERVAL_SECONDS,
                start_after=frames_info
            )
            frames_info.extend(additional)
        
        # Si hay demasiados frames, subsamplear
        if len(frames_info) > settings.MAX_FRAME_COUNT:
            frames_info = subsample_frames(frames_info, settings.MAX_FRAME_COUNT)
        
    except Exception as e:
        print(f"Error extrayendo frames: {e}")
        # Fallback: extraer por intervalo
        frames_info = extract_frames_interval(
            video_path, 
            output_dir, 
            interval_seconds=settings.FRAME_INTERVAL_SECONDS
        )
    
    return frames_info[:settings.MAX_FRAME_COUNT]


def subsample_frames(frames_info: list[dict], max_count: int) -> list[dict]:
    """
    Subsamplear frames para no exceder el máximo
    
    Estrategia: seleccionar frames equidistantes usando índices flotantes
    """
    if len(frames_info) <= max_count:
        return frames_info
    
    # Calcular índices de muestreo uniforme
    indices = [int(i * len(frames_info) / max_count) for i in range(max_count)]
    
    # Asegurar que el último frame esté incluido
    if indices[-1] != len(frames_info) - 1:
        indices[-1] = len(frames_info) - 1
    
    # Seleccionar frames únicos (evitar duplicados por redondeo)
    selected = []
    seen_indices = set()
    for idx in indices:
        if idx not in seen_indices:
            selected.append(frames_info[idx])
            seen_indices.add(idx)
    
    # Renumerar frames
    for idx, frame in enumerate(selected):
        frame["frame_num"] = idx + 1
    
    return selected


def extract_frames_interval(
    video_path: str,
    output_dir: Path,
    interval_seconds: int = 30,
    start_after: Optional[list] = None
) -> list[dict]:
    """
    Extraer frames por intervalo de tiempo (fallback)
    
    start_after: Lista de frames ya extraídos para evitar duplicados
    """
    frames_info = []
    
    try:
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / fps if fps > 0 else 0
        
        existing_timestamps = set()
        if start_after:
            existing_timestamps = {f["timestamp"] for f in start_after}
        
        idx = len(start_after) if start_after else 0
        current_time = 0
        
        while current_time < duration:
            if current_time not in existing_timestamps:
                frame_num = int(current_time * fps)
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
                ret, frame = cap.read()
                
                if ret:
                    timestamp_str = format_timestamp_for_filename(current_time)
                    frame_filename = f"frame_{idx + 1:03d}_{timestamp_str}.jpg"
                    frame_path = output_dir / frame_filename
                    
                    # Redimensionar si es muy grande
                    height, width = frame.shape[:2]
                    if width > 1920:
                        scale = 1920 / width
                        new_width = int(width * scale)
                        new_height = int(height * scale)
                        frame = cv2.resize(frame, (new_width, new_height))
                    
                    cv2.imwrite(str(frame_path), frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                    
                    frames_info.append({
                        "frame_num": idx + 1,
                        "timestamp": current_time,
                        "path": str(frame_path),
                        "filename": frame_filename
                    })
                    idx += 1
            
            current_time += interval_seconds
        
        cap.release()
        
    except Exception as e:
        print(f"Error extrayendo frames por intervalo: {e}")
    
    return frames_info

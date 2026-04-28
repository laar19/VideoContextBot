from fpdf import FPDF
from pathlib import Path
from datetime import datetime
from typing import Optional
import os
from app.processor.utils import format_timestamp


class VideoContextPDF(FPDF):
    """Clase personalizada para generar PDF del contexto del video"""
    
    def __init__(self, video_filename: str, has_audio: bool, duration: str):
        super().__init__()
        self.video_filename = video_filename
        self.has_audio = has_audio
        self.duration = duration
        self.processing_date = datetime.now().strftime("%d/%m/%Y %H:%M")
        
        # Configurar fuente Unicode
        try:
            # Intentar cargar DejaVu Sans para soporte Unicode completo
            dejavu_path = "/usr/share/fonts/truetype/dejavu"
            self.add_font('DejaVu', '', f'{dejavu_path}/DejaVuSans.ttf', uni=True)
            self.add_font('DejaVu', 'B', f'{dejavu_path}/DejaVuSans-Bold.ttf', uni=True)
            self.add_font('DejaVu', 'I', f'{dejavu_path}/DejaVuSans-Oblique.ttf', uni=True)
            self.unicode_font = 'DejaVu'
        except Exception as e:
            print(f"No se pudo cargar DejaVu: {e}")
            self.unicode_font = None
    
    def _set_unicode_font(self, style='', size=10):
        """Configurar fuente con soporte Unicode"""
        if self.unicode_font:
            self.set_font(self.unicode_font, style, size)
        else:
            # Fallback: usar Arial y evitar caracteres problemáticos
            self.set_font('Arial', style, size)
    
    def header(self):
        """Header simple en cada página"""
        # Usar font que soporte Unicode
        try:
            self.set_font('DejaVu', 'I', 8)
        except:
            self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f"VideoContextBot - {self.video_filename[:50]}", 0, 1, 'R')
        self.ln(5)
    
    def footer(self):
        """Footer con número de página"""
        try:
            self.set_font('DejaVu', 'I', 8)
        except:
            self.set_font('Arial', 'I', 8)
        self.set_y(-15)
        self.cell(0, 10, f"Página {self.page_no()}", 0, 0, 'C')
    
    def add_portada(self, additional_notes: Optional[str] = None):
        """Agregar portada del PDF"""
        self.add_page()
        
        # Título
        self._set_unicode_font('B', 24)
        self.cell(0, 30, "VideoContextBot", 0, 1, 'C')
        self.ln(10)
        
        self._set_unicode_font('B', 16)
        self.cell(0, 20, "Informe de Procesamiento", 0, 1, 'C')
        self.ln(20)
        
        # Información del video
        self._set_unicode_font('', 12)
        
        info_y = self.get_y()
        self.set_x(20)
        self.multi_cell(0, 10, f"Archivo: {self.video_filename}", 0, 'L')
        
        self.set_x(20)
        self.multi_cell(0, 10, f"Duración: {self.duration}", 0, 'L')
        
        self.set_x(20)
        audio_status = "Con audio" if self.has_audio else "Sin audio"
        self.multi_cell(0, 10, f"Estado de audio: {audio_status}", 0, 'L')
        
        self.set_x(20)
        self.multi_cell(0, 10, f"Fecha de procesamiento: {self.processing_date}", 0, 'L')
        
        # Notas adicionales (si existen)
        if additional_notes:
            self.ln(15)
            self._set_unicode_font('B', 12)
            self.cell(0, 10, "Notas Adicionales:", 0, 1, 'L')
            self._set_unicode_font('', 10)
            self.set_x(20)
            self.multi_cell(0, 8, additional_notes, 0, 'L')
        
        # Nota sobre audio
        self.ln(20)
        self.set_font('Arial', 'I', 10)
        if not self.has_audio:
            self.set_text_color(200, 0, 0)
            self.cell(0, 10, "NOTA: Este video no contiene pista de audio.", 0, 1, 'C')
            self.set_text_color(0, 0, 0)
        else:
            self.cell(0, 10, "Video con audio transcrito mediante Whisper API", 0, 1, 'C')
    
    def add_frame_with_transcription(
        self,
        frame_path: str,
        frame_num: int,
        timestamp: float,
        transcription_segments: list[str]
    ):
        """Agregar frame con su transcripción correspondiente"""
        self.add_page()
        
        # Timestamp y número de frame
        self.set_font('Arial', 'B', 12)
        timestamp_str = format_timestamp(timestamp)
        self.cell(0, 10, f"Frame {frame_num} - {timestamp_str}", 0, 1, 'L')
        
        # Imagen del frame
        try:
            # Calcular dimensiones para mantener aspect ratio
            page_width = self.w - 40  # Márgenes
            page_height = self.h - 60  # Espacio para header/footer/texto
            
            img_info = self.image(frame_path, x=20, y=self.get_y(), w=page_width)
            
            # Obtener altura real de la imagen
            img_height = img_info[2] if isinstance(img_info, tuple) else 100
            
            # Mover cursor debajo de la imagen
            self.ln(img_height + 5)
            
        except Exception as e:
            print(f"Error insertando imagen {frame_path}: {e}")
            self.cell(0, 10, f"[Imagen no disponible: {Path(frame_path).name}]", 0, 1, 'L')
            self.ln(10)
        
        # Transcripción relevante
        if transcription_segments:
            self.set_font('Arial', 'B', 10)
            self.cell(0, 8, "Transcripción relevante (±15s):", 0, 1, 'L')
            
            self.set_font('Arial', '', 9)
            self.set_fill_color(240, 240, 240)
            self.set_x(10)
            
            # Combinar segmentos en un texto
            full_text = " ".join(transcription_segments)
            
            # Multi_cell con fondo
            self.multi_cell(
                190, 6,
                full_text,
                0, 'L', fill=True
            )
        else:
            self.set_font('Arial', 'I', 9)
            self.set_text_color(150, 150, 150)
            self.cell(0, 10, "(Sin transcripción en este segmento)", 0, 1, 'L')
            self.set_text_color(0, 0, 0)
    
    def add_no_audio_section(self):
        """Agregar sección especial para videos sin audio"""
        self.add_page()
        
        self.set_font('Arial', 'B', 14)
        self.cell(0, 15, "Información sobre el Audio", 0, 1, 'L')
        
        self.set_font('Arial', '', 11)
        self.set_text_color(200, 0, 0)
        self.multi_cell(
            0, 10,
            "Este video NO contiene pista de audio. "
            "Por lo tanto, no se ha generado transcripción. "
            "Las capturas de pantalla se han extraído normalmente "
            "basándose en los cambios visuales detectados.",
            0, 'L'
        )
        self.set_text_color(0, 0, 0)
    
    def add_summary_section(self, total_frames: int, total_segments: int = 0):
        """Agregar sección de resumen al final"""
        self.add_page()
        
        self.set_font('Arial', 'B', 14)
        self.cell(0, 15, "Resumen del Procesamiento", 0, 1, 'L')
        
        self.set_font('Arial', '', 11)
        
        lines = [
            f"Total de frames extraídos: {total_frames}",
        ]
        
        if self.has_audio:
            lines.append(f"Segmentos de transcripción: {total_segments}")
        
        for line in lines:
            self._set_unicode_font('', 11)
            self.cell(0, 8, f"- {line}", 0, 1, 'L')
        
        self.ln(15)
        self._set_unicode_font('I', 9)
        self.set_text_color(100, 100, 100)
        self.cell(0, 10, "Generado por VideoContextBot", 0, 1, 'C')


def generate_pdf(
    output_folder: Path,
    video_filename: str,
    has_audio: bool,
    duration: str,
    frames_info: list[dict],
    transcription_result: Optional[dict] = None,
    additional_notes: Optional[str] = None
) -> str:
    """
    Generar PDF completo con frames y transcripción
    
    Returns: path al PDF generado
    """
    pdf = VideoContextPDF(video_filename, has_audio, duration)
    
    # Intentar agregar font Unicode para soportar caracteres especiales
    try:
        # DejaVu Sans es común en sistemas Linux
        pdf.add_font('DejaVu', '', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', uni=True)
        pdf.add_font('DejaVu', 'B', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', uni=True)
        pdf.add_font('DejaVu', 'I', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf', uni=True)
    except Exception as e:
        print(f"No se pudo cargar DejaVu, usando Arial: {e}")
    
    # Portada
    pdf.add_portada(additional_notes)
    
    # Sección especial si no hay audio
    if not has_audio:
        pdf.add_no_audio_section()
    
    # Frames con transcripción
    for frame in frames_info:
        transcription_segments = []
        
        if has_audio and transcription_result:
            # Obtener segmentos relevantes para este timestamp
            transcription_segments = get_segments_for_timestamp(
                transcription_result,
                frame["timestamp"],
                window_seconds=15.0
            )
        
        pdf.add_frame_with_transcription(
            frame_path=frame["path"],
            frame_num=frame["frame_num"],
            timestamp=frame["timestamp"],
            transcription_segments=transcription_segments
        )
    
    # Resumen final
    total_segments = len(transcription_result.get("segments", [])) if transcription_result else 0
    pdf.add_summary_section(len(frames_info), total_segments)
    
    # Guardar PDF
    pdf_path = output_folder / "report.pdf"
    pdf_output = str(pdf_path)
    pdf.output(pdf_output)
    
    return pdf_output


def get_segments_for_timestamp(transcription_result: dict, timestamp: float, window_seconds: float = 15.0) -> list[str]:
    """Helper para obtener segmentos relevantes"""
    segments = transcription_result.get("segments", [])
    relevant = []
    
    window_half = window_seconds / 2
    start_time = timestamp - window_half
    end_time = timestamp + window_half
    
    for segment in segments:
        seg_start = segment.get("start", 0)
        seg_end = segment.get("end", 0)
        
        if seg_start <= end_time and seg_end >= start_time:
            relevant.append(segment.get("text", "").strip())
    
    return relevant

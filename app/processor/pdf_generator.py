from fpdf import FPDF
from pathlib import Path
from typing import Optional
from app.processor.utils import format_timestamp


class VideoContextPDF(FPDF):
    """Clase personalizada para generar PDF del contexto del video"""
    
    def __init__(self, video_filename: str, has_audio: bool, duration: str):
        super().__init__()
        self.video_filename = video_filename
        self.has_audio = has_audio
        self.duration = duration
        
        # Configurar fuente Unicode
        try:
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
            self.set_font('Arial', style, size)
    
    def add_frame_with_transcription(
        self,
        frame_path: str,
        frame_num: int,
        timestamp: float,
        transcription_segments: list[str]
    ):
        """Agregar frame con transcripción ENCIMA"""
        self.add_page()
        
        # Timestamp
        self._set_unicode_font('B', 11)
        timestamp_str = format_timestamp(timestamp)
        self.cell(0, 8, f"[{timestamp_str}] Frame {frame_num}", 0, 1, 'L')
        
        # Transcripción relevante (ARRIBA de la imagen)
        if transcription_segments:
            self._set_unicode_font('', 9)
            self.set_fill_color(245, 245, 245)
            self.set_x(10)
            
            # Combinar segmentos en un texto
            full_text = " ".join(transcription_segments)
            
            # Multi_cell con fondo
            self.multi_cell(
                190, 5,
                full_text,
                0, 'L', fill=True
            )
            
            self.ln(3)
        
        # Imagen del frame
        try:
            page_width = self.w - 40  # Márgenes
            
            img_info = self.image(frame_path, x=20, y=self.get_y(), w=page_width)
            
            # Obtener altura real de la imagen
            img_height = img_info[2] if isinstance(img_info, tuple) else 100
            
            # Mover cursor debajo de la imagen
            self.ln(img_height + 5)
            
        except Exception as e:
            print(f"Error insertando imagen {frame_path}: {e}")
            self.cell(0, 10, f"[Imagen no disponible: {Path(frame_path).name}]", 0, 1, 'L')
            self.ln(10)


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

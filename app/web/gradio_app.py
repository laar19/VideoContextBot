import gradio as gr
import asyncio
from pathlib import Path
from datetime import datetime
from app.config import settings
from app.database import SessionLocal
from app.models import Job, JobStatus
from app.tasks import process_video_task
from app.processor.utils import generate_job_id, create_temp_folder, validate_video_file
import time
import shutil


def process_video_gradio(
    video_file,
    notes_text,
    notes_file,
    progress=gr.Progress()
):
    """
    Procesar video desde interfaz Gradio
    
    Returns: (mensaje, PDF, ZIP, logs)
    """
    if video_file is None:
        return "❌ Error: Debes subir un video", None, None, ""
    
    job_id = generate_job_id()
    temp_dir = create_temp_folder(job_id)
    
    # Copiar video a temp
    video_path = temp_dir / f"video_{Path(video_file).name}"
    shutil.copy(video_file, video_path)
    
    # Validar video
    is_valid, error_msg = validate_video_file(str(video_path))
    if not is_valid:
        return f"❌ Error: {error_msg}", None, None, ""
    
    # Combinar notas
    additional_notes = notes_text or ""
    if notes_file:
        try:
            with open(notes_file, "r", encoding="utf-8") as f:
                file_notes = f.read()
                if additional_notes:
                    additional_notes += "\n\n--- Archivo de notas ---\n" + file_notes
                else:
                    additional_notes = file_notes
        except Exception as e:
            additional_notes += f"\n\n[Error leyendo archivo de notas: {e}]"
    
    # Crear job en DB
    db = SessionLocal()
    try:
        job = Job(
            job_id=job_id,
            status=JobStatus.PENDING,
            video_path=str(video_path),
            video_filename=Path(video_file).name,
            additional_notes=additional_notes if additional_notes else None,
            source="web",
            progress=0,
            progress_message="Esperando procesamiento..."
        )
        db.add(job)
        db.commit()
    finally:
        db.close()
    
    # Encolar tarea Celery
    process_video_task.delay(
        job_id=job_id,
        video_path=str(video_path),
        additional_notes=additional_notes if additional_notes else None
    )
    
    # Esperar y mostrar progreso
    log_lines = [f"[{datetime.now().strftime('%H:%M:%S')}] Job iniciado: {job_id[:8]}"]
    
    db = SessionLocal()
    try:
        for _ in range(300):  # Máximo 5 minutos de espera (300 * 1s)
            job = db.query(Job).filter(Job.job_id == job_id).first()
            if not job:
                break
            
            log_lines.append(
                f"[{datetime.now().strftime('%H:%M:%S')}] "
                f"Progreso: {job.progress}% - {job.progress_message}"
            )
            
            progress(job.progress / 100)
            
            if job.status == JobStatus.COMPLETED:
                log_lines.append(f"[{datetime.now().strftime('%H:%M:%S')}] ¡Completado!")
                
                # Preparar downloads
                pdf_path = job.pdf_path
                zip_path = job.zip_path
                
                if pdf_path and Path(pdf_path).exists() and zip_path and Path(zip_path).exists():
                    return (
                        "✅ ¡Procesamiento completado! Descarga los archivos abajo.",
                        pdf_path,
                        zip_path,
                        "\n".join(log_lines)
                    )
                else:
                    return "❌ Error: Archivos de output no encontrados", None, None, "\n".join(log_lines)
            
            elif job.status == JobStatus.FAILED:
                log_lines.append(f"[{datetime.now().strftime('%H:%M:%S')}] Error: {job.error_message}")
                return f"❌ Error: {job.error_message}", None, None, "\n".join(log_lines)
            
            time.sleep(1)
        
        log_lines.append(f"[{datetime.now().strftime('%H:%M:%S')}] Timeout: Procesamiento muy largo")
        return (
            "⏳ El procesamiento está tomando más de lo esperado. "
            "Puedes descargar los archivos más tarde desde la API o esperar.",
            None,
            None,
            "\n".join(log_lines)
        )
        
    finally:
        db.close()


def create_gradio_app():
    """Crear interfaz Gradio"""
    
    with gr.Blocks(
        title="VideoContextBot",
        theme=gr.themes.Soft(),
        css="""
        .gradio-container {max-width: 900px !important;}
        .output-file {margin: 10px 0;}
        """
    ) as demo:
        
        gr.Markdown(
            """
            # 🎬 VideoContextBot
            
            Procesa videos de grabaciones de pantalla y genera contexto rico para agentes de IA.
            
            **Características:**
            - 🎯 Extracción inteligente de frames únicos
            - 🎤 Transcripción de audio con Whisper API
            - 📄 Generación de PDF profesional
            - 📦 Descarga completa en ZIP
            """
        )
        
        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown("### 📤 Subir Video")
                
                video_input = gr.File(
                    label="Video",
                    file_types=[".mp4", ".mkv", ".avi", ".mov", ".webm"],
                    type="filepath"
                )
                
                gr.Markdown("### 📝 Notas Adicionales (Opcional)")
                
                notes_text = gr.Textbox(
                    label="Pegar notas/logs",
                    placeholder="Pega aquí cualquier nota, log o información adicional...",
                    lines=5
                )
                
                notes_file = gr.File(
                    label="O subir archivo .txt",
                    file_types=[".txt"],
                    type="filepath"
                )
                
                process_btn = gr.Button(
                    "🚀 Procesar Video",
                    variant="primary",
                    size="lg"
                )
            
            with gr.Column(scale=1):
                gr.Markdown("### 📥 Resultados")
                
                status_output = gr.Textbox(
                    label="Estado",
                    interactive=False
                )
                
                pdf_output = gr.File(
                    label="📄 PDF Report",
                    interactive=False
                )
                
                zip_output = gr.File(
                    label="📦 ZIP Completo",
                    interactive=False
                )
                
                progress_bar = gr.Slider(
                    label="Progreso",
                    minimum=0,
                    maximum=100,
                    value=0,
                    interactive=False
                )
        
        gr.Markdown("### 📋 Logs de Procesamiento")
        logs_output = gr.Textbox(
            label="Logs",
            lines=10,
            max_lines=20,
            interactive=False
        )
        
        gr.Markdown(
            """
            ---
            **ℹ️ Información:**
            - Tamaño máximo: 2GB
            - Formatos: MP4, MKV, AVI, MOV, WebM
            - El procesamiento puede tomar varios minutos dependiendo del tamaño del video
            """
        )
        
        # Conectar botón
        process_btn.click(
            fn=process_video_gradio,
            inputs=[video_input, notes_text, notes_file],
            outputs=[status_output, pdf_output, zip_output, logs_output]
        )
    
    return demo


def launch_app():
    """Lanzar aplicación Gradio"""
    demo = create_gradio_app()
    demo.launch(
        server_name="0.0.0.0",
        server_port=settings.GRADIO_PORT,
        share=False
    )


if __name__ == "__main__":
    launch_app()

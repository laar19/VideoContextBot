import gradio as gr
import json
import os
from pathlib import Path
from datetime import datetime
from app.config import settings
from app.database import SessionLocal
from app.models import Job, JobStatus
from app.tasks import process_video_task
from app.processor.utils import generate_job_id, create_temp_folder, validate_video_file
import time
import shutil


# Archivo para persistencia del intervalo
FRAME_INTERVAL_FILE = "/app/data/gradio_frame_interval.json"


def load_frame_interval() -> int:
    """Cargar intervalo guardado (persistente entre recargas)"""
    try:
        path = Path(FRAME_INTERVAL_FILE)
        if path.exists():
            with open(path, "r") as f:
                data = json.load(f)
                return data.get("interval", 0)
    except Exception as e:
        print(f"Error cargando intervalo: {e}")
    return 0


def save_frame_interval(value: int):
    """Guardar intervalo (persistente entre recargas)"""
    try:
        path = Path(FRAME_INTERVAL_FILE)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump({"interval": value}, f)
    except Exception as e:
        print(f"Error guardando intervalo: {e}")


def process_video_gradio(video_file, notes_text, notes_file, frame_interval, progress=gr.Progress()):
    """
    Procesar video desde interfaz Gradio
    
    Returns: (mensaje, PDF, ZIP, logs, job_id, cancel_btn_visible)
    """
    if video_file is None:
        return "❌ Error: Debes subir un video", None, None, "", None, False
    
    job_id = generate_job_id()
    temp_dir = create_temp_folder(job_id)
    
    # Copiar video a temp
    video_path = temp_dir / f"video_{Path(video_file).name}"
    shutil.copy(video_file, video_path)
    
    # Validar video
    is_valid, error_msg = validate_video_file(str(video_path))
    if not is_valid:
        return f"❌ Error: {error_msg}", None, None, "", None, False
    
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
    
    # frame_interval: 0 = Auto (scene detection), >0 = segundos entre capturas
    fi = frame_interval if frame_interval and frame_interval > 0 else None
    
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
            progress_message="Esperando procesamiento...",
            frame_interval=fi
        )
        db.add(job)
        db.commit()
    finally:
        db.close()
    
    # Encolar tarea Celery
    process_video_task.delay(
        job_id=job_id,
        video_path=str(video_path),
        additional_notes=additional_notes if additional_notes else None,
        frame_interval=fi
    )
    
    # Esperar y mostrar progreso con polling no bloqueante
    log_lines = [f"[{datetime.now().strftime('%H:%M:%S')}] Job iniciado: {job_id[:8]}"]
    
    db = SessionLocal()
    try:
        # Polling: 120 iteraciones * 3s = 360s = 6 minutos máximo
        for iteration in range(120):
            job = db.query(Job).filter(Job.job_id == job_id).first()
            if not job:
                break
            
            # FORZAR refresh desde DB para obtener datos actualizados
            db.expire_all()  # Fix: expire_all() no lleva argumentos
            
            log_lines.append(
                f"[{datetime.now().strftime('%H:%M:%S')}] "
                f"Progreso: {job.progress}% - {job.progress_message}"
            )
            
            # Actualizar barra de progreso
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
                        "\n".join(log_lines),
                        job_id,
                        False  # Ocultar botón cancelar
                    )
                else:
                    return "❌ Error: Archivos de output no encontrados", None, None, "\n".join(log_lines), None, False
            
            elif job.status == JobStatus.FAILED:
                log_lines.append(f"[{datetime.now().strftime('%H:%M:%S')}] Error: {job.error_message}")
                return f"❌ Error: {job.error_message}", None, None, "\n".join(log_lines), None, False
            
            time.sleep(3)  # Poll cada 3 segundos (reducido de 2s para menos carga)
        
        log_lines.append(f"[{datetime.now().strftime('%H:%M:%S')}] Timeout: Procesamiento muy largo (>6 min)")
        return (
            "⏳ El procesamiento está tomando más de 6 minutos. "
            "Puedes descargar los archivos más tarde desde la API o usar el bot de Telegram.",
            None,
            None,
            "\n".join(log_lines),
            job_id,
            False  # Ocultar botón cancelar después de timeout
        )
        
    finally:
        db.close()


def show_cancel_button_on_start(job_id, video_input):
    """Mostrar botón cancelar inmediatamente al iniciar procesamiento"""
    if video_input is not None:
        return job_id, True  # Mostrar botón cancelar
    return None, False


def cancel_current_job(job_id):
    """Cancelar job actual"""
    if job_id:
        try:
            from app.tasks import delete_job_files_task
            delete_job_files_task.delay(job_id=job_id)
            return "❌ Proceso cancelado por usuario", None, None, ["Proceso cancelado"], None, False
        except Exception as e:
            return f"❌ Error al cancelar: {e}", None, None, [], None, False
    return "No hay proceso activo", None, None, [], None, False


def create_gradio_app():
    """Crear interfaz Gradio"""
    
    with gr.Blocks(
        title="VideoContextBot"
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
                
                gr.Markdown("### 🎯 Intervalo de Captura")
                
                frame_interval = gr.Slider(
                    label="Segundos entre capturas (0 = Auto / detección de escenas)",
                    minimum=0,
                    maximum=30,
                    step=1,
                    value=load_frame_interval()
                )
                
                gr.Markdown(
                    "Valores recomendados: 1, 2, 3, 5, 9, 30<br>"
                    "Se guarda automáticamente en tu navegador."
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
        
        # Estado oculto para job_id
        job_id_state = gr.State(value=None)
        
        # Estado para intervalo (cargado desde disco al iniciar)
        default_interval = load_frame_interval()
        frame_interval_state = gr.State(value=default_interval)
        
        gr.Markdown(
            """
            ---
            **ℹ️ Información:**
            - Tamaño máximo: 2GB
            - Formatos: MP4, MKV, AVI, MOV, WebM
            - El procesamiento puede tomar varios minutos dependiendo del tamaño del video
            - Usá el bot de Telegram para procesamiento más rápido
            """
        )
        
        # Botón de cancelar (visible cuando hay procesamiento activo)
        cancel_btn = gr.Button("❌ Cancelar Proceso", variant="stop", visible=False)
        
        # Conectar botón de procesar
        process_btn.click(
            fn=process_video_gradio,
            inputs=[video_input, notes_text, notes_file, frame_interval],
            outputs=[status_output, pdf_output, zip_output, logs_output, job_id_state, cancel_btn]
        ).then(
            fn=lambda: None,
            inputs=[],
            outputs=[]
        )
        
        # Persistir intervalo al cambiar (guarda a disco entre recargas)
        frame_interval.change(
            fn=save_frame_interval,
            inputs=[frame_interval],
            outputs=[]
        )
        
        # Conectar botón de cancelar
        cancel_btn.click(
            fn=cancel_current_job,
            inputs=[job_id_state],
            outputs=[status_output, pdf_output, zip_output, logs_output, job_id_state, cancel_btn]
        )
    
    return demo


def launch_app():
    """Lanzar aplicación Gradio"""
    demo = create_gradio_app()
    demo.launch(
        server_name="0.0.0.0",
        server_port=settings.GRADIO_PORT,
        share=False,
        theme=gr.themes.Soft(),
        css="""
        .gradio-container {max-width: 900px !important;}
        .output-file {margin: 10px 0;}
        """
    )


if __name__ == "__main__":
    launch_app()

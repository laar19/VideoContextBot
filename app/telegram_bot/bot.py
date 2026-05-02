import logging
import json
import os
from telegram import Update, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
    ConversationHandler
)
from telegram.constants import ChatAction
from app.config import settings
from app.database import SessionLocal
from app.models import Job, JobStatus
from app.tasks import process_video_task, delete_job_files_task
from app.processor.utils import generate_job_id, create_temp_folder, validate_video_file
from pathlib import Path
import uuid

# Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=getattr(logging, settings.LOG_LEVEL)
)
logger = logging.getLogger(__name__)

# Estados de conversación
WAITING_NOTES, WAITING_FILE = range(2)

# Almacenamiento temporal de datos de usuario
user_data_store = {}

# Archivo para persistencia de intervalos
INTERVAL_STORE_PATH = "/app/data/user_intervals.json"


def load_user_intervals() -> dict:
    """Cargar intervalos persistentes por usuario"""
    try:
        path = Path(INTERVAL_STORE_PATH)
        if path.exists():
            with open(path, "r") as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Error cargando intervalos: {e}")
    return {}


def save_user_intervals(intervals: dict):
    """Guardar intervalos persistentes por usuario"""
    try:
        path = Path(INTERVAL_STORE_PATH)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(intervals, f, indent=2)
    except Exception as e:
        logger.error(f"Error guardando intervalos: {e}")


def get_user_interval(user_id: int) -> int | None:
    """Obtener intervalo guardado del usuario (None = Auto)"""
    intervals = load_user_intervals()
    val = intervals.get(str(user_id), 0)
    return val if val > 0 else None


def set_user_interval(user_id: int, interval: int):
    """Guardar intervalo del usuario"""
    intervals = load_user_intervals()
    intervals[str(user_id)] = interval
    save_user_intervals(intervals)


def is_authorized(user_id: int) -> bool:
    """Verificar si el usuario está autorizado para usar el bot"""
    allowed_ids = settings.allowed_user_ids
    
    # Si no hay IDs configurados, permitir todos (para testing)
    if not allowed_ids:
        logger.warning("No hay ALLOWED_USER_IDS configurados. Permitiendo todos los usuarios.")
        return True
    
    return user_id in allowed_ids


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /start"""
    user = update.effective_user
    
    if not is_authorized(user.id):
        await update.message.reply_text(
            "❌ Lo siento, no estás autorizado para usar este bot.\n"
            "Contacta al administrador para que agregue tu ID de usuario."
        )
        return
    
    welcome_text = (
        f"¡Hola {user.first_name}! 👋\n\n"
        "Soy *VideoContextBot*, un bot que procesa videos de grabaciones de pantalla "
        "y genera contexto rico para agentes de IA.\n\n"
        "¿Qué puedo hacer?\n"
        "• 🎬 Extraer frames únicos de tu video\n"
        "• 🎤 Transcribir audio (si tiene) con Whisper API\n"
        "• 📄 Generar un PDF profesional con todo el contexto\n"
        "• 📦 Entregar un ZIP con todo el output\n\n"
        "Para comenzar, envíame un video o usa /ayuda para más información."
    )
    
    await update.message.reply_text(welcome_text, parse_mode='Markdown')


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /ayuda"""
    user = update.effective_user
    
    if not is_authorized(user.id):
        return
    
    help_text = (
        "📖 *Guía de Uso*\n\n"
        "*1. Enviar Video:*\n"
        "Envía un video como archivo de video o documento.\n"
        "Formatos soportados: MP4, MKV, AVI, MOV, WebM\n"
        "Tamaño máximo: 2GB\n\n"
        "*2. Añadir Notas (opcional):*\n"
        "Después del video, puedes enviarme notas o logs adicionales.\n"
        "También puedes subir un archivo .txt\n\n"
        "*3. Procesamiento:*\n"
        "Procesaré el video en background y te notificaré cuando esté listo.\n\n"
        "*4. Resultados:*\n"
        "Recibirás:\n"
        "• 📄 PDF con frames y transcripción\n"
        "• 📦 ZIP con toda la carpeta de output\n\n"
        "*Comandos:*\n"
        "/start - Iniciar el bot\n"
        "/ayuda - Mostrar esta ayuda\n"
        "/estado - Ver jobs en progreso\n"
        "/cancelar - Cancelar job actual\n"
        "/interval - Configurar intervalo de captura de frames\n"
        "  Ej: /interval 5 (cada 5 segundos)\n"
        "  Ej: /interval auto (detección de escenas)"
    )
    
    await update.message.reply_text(help_text, parse_mode='Markdown')


async def set_interval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /interval - Configurar intervalo de captura de frames"""
    user = update.effective_user

    if not is_authorized(user.id):
        return

    args = context.args
    if not args:
        current = get_user_interval(user.id)
        if current:
            msg = (
                f"📸 *Intervalo actual:* {current} segundos\n\n"
                "Para cambiarlo, usa:\n"
                "`/interval <segundos>` (1, 2, 3, 5, 9, 30...)\n"
                "`/interval auto` (detección de escenas)"
            )
        else:
            msg = (
                "📸 *Intervalo actual:* Auto (detección de escenas)\n\n"
                "Para cambiarlo, usa:\n"
                "`/interval <segundos>` (1, 2, 3, 5, 9, 30...)\n"
                "`/interval auto` (detección de escenas)"
            )
        await update.message.reply_text(msg, parse_mode='Markdown')
        return

    if args[0].lower() == "auto":
        set_user_interval(user.id, 0)
        await update.message.reply_text(
            "✅ Intervalo configurado a *Auto* (detección de escenas).\n\n"
            "Los próximos videos usarán detección inteligente de escenas.",
            parse_mode='Markdown'
        )
        return

    try:
        seconds = int(args[0])
        if seconds < 1:
            await update.message.reply_text("❌ El intervalo debe ser al menos 1 segundo.")
            return
        if seconds > 300:
            await update.message.reply_text("❌ El intervalo máximo es 300 segundos (5 minutos).")
            return

        set_user_interval(user.id, seconds)
        await update.message.reply_text(
            f"✅ Intervalo configurado a *{seconds} segundos*.\n\n"
            f"Los próximos videos capturarán un frame cada {seconds} segundos.",
            parse_mode='Markdown'
        )
    except ValueError:
        await update.message.reply_text(
            "❌ Usá: `/interval <segundos>` o `/interval auto`\n"
            "Ej: `/interval 5` para capturar cada 5 segundos",
            parse_mode='Markdown'
        )


async def receive_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manejar recepción de video"""
    user = update.effective_user
    
    if not is_authorized(user.id):
        return
    
    # Obtener archivo de video
    video_file = None
    file_name = "video.mp4"  # Por defecto
    
    if update.message.video:
        video_file = update.message.video
        file_name = video_file.file_name or f"video_{user.id}.mp4"
    elif update.message.document:
        # Verificar que sea video por mime_type
        if not update.message.document.mime_type.startswith('video/'):
            await update.message.reply_text(
                "⚠️ El archivo debe ser un video. Por favor envíalo nuevamente."
            )
            return
        video_file = update.message.document
        file_name = video_file.file_name or f"video_{user.id}.mp4"
        
        # Asegurar que tenga extensión válida
        if '.' not in file_name:
            # Extraer extensión del mime_type
            mime_to_ext = {
                'video/mp4': '.mp4',
                'video/x-matroska': '.mkv',
                'video/avi': '.avi',
                'video/quicktime': '.mov',
                'video/webm': '.webm'
            }
            ext = mime_to_ext.get(update.message.document.mime_type, '.mp4')
            file_name = f"{file_name}{ext}"
    else:
        return
    
    # Verificar tamaño
    if video_file.file_size > settings.max_video_size_bytes:
        await update.message.reply_text(
            f"❌ Archivo muy grande: {video_file.file_size / 1024 / 1024:.1f}MB\n"
            f"Tamaño máximo: {settings.MAX_VIDEO_SIZE_MB}MB"
        )
        return
    
    # Guardar datos temporales
    user_data_store[user.id] = {
        "video_file": video_file,
        "file_name": file_name,
        "notes": None,
        "job_id": None,
        "frame_interval": get_user_interval(user.id)
    }
    
    # Descargar video
    await update.message.reply_chat_action(ChatAction.UPLOAD_DOCUMENT)
    
    job_id = generate_job_id()
    temp_dir = create_temp_folder(job_id)
    video_path = temp_dir / f"video_{file_name}"
    
    file = await context.bot.get_file(video_file.file_id)
    await file.download_to_drive(str(video_path))
    
    # Validar video
    is_valid, error_msg = validate_video_file(str(video_path))
    if not is_valid:
        await update.message.reply_text(f"❌ Error: {error_msg}")
        return
    
    # Guardar path
    user_data_store[user.id]["video_path"] = str(video_path)
    user_data_store[user.id]["job_id"] = job_id
    
    # Preguntar por notas
    await update.message.reply_text(
        "✅ Video recibido correctamente.\n\n"
        "¿Deseas añadir notas o logs adicionales?\n\n"
        "• Envía un mensaje de texto con tus notas\n"
        "• O sube un archivo .txt\n"
        "• O envía /omitir para continuar sin notas"
    )
    
    return WAITING_NOTES


async def receive_notes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manejar recepción de notas"""
    user = update.effective_user
    
    if not is_authorized(user.id):
        return ConversationHandler.END
    
    user_data = user_data_store.get(user.id)
    if not user_data:
        await update.message.reply_text(
            "⚠️ Sesión expirada. Por favor envía el video nuevamente."
        )
        return ConversationHandler.END
    
    # Manejar texto o archivo
    notes = None
    
    if update.message.text and update.message.text != "/omitir":
        notes = update.message.text
    elif update.message.document:
        if update.message.document.file_name.endswith('.txt'):
            file = await context.bot.get_file(update.message.document.file_id)
            txt_content = await file.download_as_bytearray()
            notes = txt_content.decode('utf-8')
        else:
            await update.message.reply_text(
                "⚠️ El archivo debe ser .txt. Envía tus notas como texto o /omitir"
            )
            return WAITING_NOTES
    
    user_data["notes"] = notes
    
    # Crear job en DB
    db = SessionLocal()
    try:
        job = Job(
            job_id=user_data["job_id"],
            status=JobStatus.PENDING,
            video_path=user_data["video_path"],
            video_filename=user_data.get("file_name", "video.mp4"),
            additional_notes=notes,
            source="telegram",
            user_id=str(user.id),
            progress=0,
            progress_message="Esperando procesamiento...",
            frame_interval=user_data.get("frame_interval")
        )
        db.add(job)
        db.commit()
    finally:
        db.close()
    
    # Encolar tarea
    process_video_task.delay(
        job_id=user_data["job_id"],
        video_path=user_data["video_path"],
        additional_notes=notes,
        frame_interval=user_data.get("frame_interval")
    )
    
    interval_msg = ""
    if user_data.get("frame_interval"):
        interval_msg = f"📸 Capturando cada {user_data['frame_interval']} segundos.\n"
    
    await update.message.reply_text(
        f"🚀 ¡Procesamiento iniciado!\n\n"
        f"{interval_msg}"
        "Te notificaré cuando esté listo.\n"
        "Puedes usar /estado para ver el progreso."
    )
    
    # Limpiar datos
    user_data_store.pop(user.id, None)
    
    return ConversationHandler.END


async def skip_notes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Omitir notas y procesar directamente"""
    user = update.effective_user
    
    if not is_authorized(user.id):
        return ConversationHandler.END
    
    user_data = user_data_store.get(user.id)
    if not user_data:
        await update.message.reply_text(
            "⚠️ Sesión expirada. Por favor envía el video nuevamente."
        )
        return ConversationHandler.END
    
    # Crear job sin notas
    db = SessionLocal()
    try:
        job = Job(
            job_id=user_data["job_id"],
            status=JobStatus.PENDING,
            video_path=user_data["video_path"],
            video_filename=user_data.get("file_name", "video.mp4"),
            additional_notes=None,
            source="telegram",
            user_id=str(user.id),
            progress=0,
            progress_message="Esperando procesamiento...",
            frame_interval=user_data.get("frame_interval")
        )
        db.add(job)
        db.commit()
    finally:
        db.close()
    
    # Encolar tarea
    process_video_task.delay(
        job_id=user_data["job_id"],
        video_path=user_data["video_path"],
        additional_notes=None,
        frame_interval=user_data.get("frame_interval")
    )
    
    interval_msg = ""
    if user_data.get("frame_interval"):
        interval_msg = f"📸 Capturando cada {user_data['frame_interval']} segundos.\n"
    
    await update.message.reply_text(
        f"🚀 ¡Procesamiento iniciado!\n\n"
        f"{interval_msg}"
        "Te notificaré cuando esté listo."
    )
    
    user_data_store.pop(user.id, None)
    
    return ConversationHandler.END


async def check_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /estado"""
    user = update.effective_user
    
    if not is_authorized(user.id):
        return
    
    db = SessionLocal()
    try:
        # Buscar SOLO el job más reciente del usuario
        job = db.query(Job).filter(
            Job.user_id == str(user.id)
        ).order_by(Job.created_at.desc()).first()
        
        if not job:
            await update.message.reply_text("No tienes jobs registrados.")
            return
        
        # Solo procesar el job más reciente
        if job.status in [JobStatus.PENDING, JobStatus.PROCESSING]:
            status_emoji = "⏳" if job.status == JobStatus.PENDING else "🔄"
            text = (
                f"{status_emoji} Job {job.job_id[:8]}\n"
                f"Archivo: {job.video_filename}\n"
                f"Progreso: {job.progress}%\n"
                f"Estado: {job.progress_message}"
            )
            await update.message.reply_text(text)
        elif job.status == JobStatus.COMPLETED:
            text = (
                f"✅ Job {job.job_id[:8]} - COMPLETADO\n"
                f"Archivo: {job.video_filename}\n"
                f"Duración: {job.video_duration or 'N/A'}\n"
                f"PDF: {job.pdf_path.split('/')[-1] if job.pdf_path else 'N/A'}\n"
                f"ZIP: {job.zip_path.split('/')[-1] if job.zip_path else 'N/A'}"
            )
            await update.message.reply_text(text)
            
            # Enviar SOLO este job (el más reciente)
            # Enviar PDF
            if job.pdf_path and Path(job.pdf_path).exists():
                await context.bot.send_document(
                    chat_id=user.id,
                    document=open(job.pdf_path, 'rb'),
                    filename=f"{job.video_filename.rsplit('.', 1)[0]}_report.pdf",
                    caption="📄 PDF con frames y transcripción"
                )
            
            # Enviar ZIP
            if job.zip_path and Path(job.zip_path).exists():
                await context.bot.send_document(
                    chat_id=user.id,
                    document=open(job.zip_path, 'rb'),
                    filename=f"{job.video_filename.rsplit('.', 1)[0]}_output.zip",
                    caption="📦 Carpeta completa de output"
                )
        elif job.status == JobStatus.FAILED:
            text = (
                f"❌ Job {job.job_id[:8]} - FALLIDO\n"
                f"Archivo: {job.video_filename}\n"
                f"Error: {job.error_message or 'Error desconocido'}"
            )
            await update.message.reply_text(text)
    finally:
        db.close()


async def cancel_job(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /cancelar"""
    user = update.effective_user
    
    if not is_authorized(user.id):
        return
    
    db = SessionLocal()
    try:
        jobs = db.query(Job).filter(
            Job.user_id == str(user.id),
            Job.status.in_([JobStatus.PENDING, JobStatus.PROCESSING])
        ).all()
        
        if not jobs:
            await update.message.reply_text("✅ No tienes jobs activos para cancelar.")
            return
        
        for job in jobs:
            job.status = JobStatus.CANCELLED
            delete_job_files_task.delay(job_id=job.job_id)
        
        db.commit()
        await update.message.reply_text("✅ Jobs cancelados y archivos en limpieza.")
    finally:
        db.close()


async def notify_completion(job_id: str):
    """Notificar a usuario cuando job está completado (llamado desde task)"""
    # Esta función sería llamada por el worker cuando completa
    # Por ahora se maneja polling o se puede implementar con webhooks
    pass


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manejador de errores"""
    logger.error(f"Error en bot: {context.error}")
    
    if update and update.effective_message:
        await update.effective_message.reply_text(
            "❌ Ocurrió un error procesando tu solicitud.\n"
            "Por favor intenta nuevamente."
        )


def create_application() -> Application:
    """Crear y configurar la aplicación del bot"""
    application = Application.builder().token(settings.TELEGRAM_BOT_TOKEN).build()
    
    # Conversation handler para flujo de video
    conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(
                filters.VIDEO | filters.Document.MimeType("video/*"),
                receive_video
            )
        ],
        states={
            WAITING_NOTES: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_notes),
                MessageHandler(filters.Document.ALL, receive_notes),
                CommandHandler("omitir", skip_notes)
            ]
        },
        fallbacks=[
            CommandHandler("cancelar", cancel_job)
        ],
        per_message=False
    )
    
    # Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("ayuda", help_command))
    application.add_handler(CommandHandler("estado", check_status))
    application.add_handler(CommandHandler("cancelar", cancel_job))
    application.add_handler(CommandHandler("interval", set_interval))
    application.add_handler(conv_handler)
    
    # Error handler
    application.add_error_handler(error_handler)
    
    return application


async def post_init(application: Application):
    """Inicialización post-startup"""
    # Setear comandos del bot
    commands = [
        BotCommand("start", "Iniciar el bot"),
        BotCommand("ayuda", "Mostrar guía de uso"),
        BotCommand("estado", "Ver jobs en progreso"),
        BotCommand("cancelar", "Cancelar job actual"),
        BotCommand("interval", "Configurar intervalo de captura de frames")
    ]
    await application.bot.set_my_commands(commands)
    logger.info("Comandos del bot actualizados")


def run_bot():
    """Ejecutar el bot"""
    logger.info("Iniciando VideoContextBot...")
    
    application = create_application()
    application.post_init = post_init
    
    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True
    )


if __name__ == "__main__":
    run_bot()

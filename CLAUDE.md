# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

VideoContextBot processes screen-recording videos to generate rich context for AI agents. It extracts unique frames (via PySceneDetect), transcribes audio (via OpenAI-compatible Whisper APIs), and produces a professional PDF report with timestamped frames and transcription, plus a ZIP with all output files.

## Architecture

6 Docker services orchestrated via docker-compose:

- **redis** (vcb_redis) — Celery message broker
- **api** (vcb_api) — FastAPI REST server on port 8000 (`python -m app.main`)
- **celery-worker** (vcb_celery_worker) — Processes video jobs asynchronously
- **celery-beat** (vcb_celery_beat) — Periodic cleanup of old files (hourly)
- **telegram-bot** (vcb_telegram_bot) — python-telegram-bot polling (`python run_bot.py`)
- **gradio** (vcb_gradio) — Web UI on port 7860 (`python -m app.web.gradio_app`)

### Code Layout

```
app/
├── main.py              # FastAPI app + REST endpoints (/api/jobs, /health)
├── config.py             # Pydantic Settings from .env
├── database.py           # SQLAlchemy engine + session (SQLite with WAL mode)
├── models.py             # Job model (job_id, status, paths, progress, timestamps)
├── celery_app.py         # Celery app config (Redis broker, beat schedule)
├── tasks.py              # Celery tasks: process_video_task, cleanup, delete_job_files
├── processor/
│   ├── core.py           # Orquestrador: frames → transcription → PDF → ZIP
│   ├── video_utils.py    # Scene detection (PySceneDetect), frame extraction (OpenCV), audio detection (pymediainfo)
│   ├── transcription.py  # Whisper API via OpenAI SDK (provider-agnostic)
│   ├── pdf_generator.py  # PDF generation with fpdf2 (DejaVu fonts for Unicode)
│   └── utils.py          # File ops: folders, ZIP, cleanup, validation, timestamps
├── telegram_bot/
│   └── bot.py            # Telegram bot with ConversationHandler (video → notes → process)
└── web/
    └── gradio_app.py     # Gradio Blocks UI with polling progress
```

### Processing Pipeline (app/processor/core.py `process_video`)

1. Create output folder → 2. Get video info (audio?, duration) → 3. Extract frames (scene detection or interval-based) → 4. Transcribe audio via Whisper (if present) → 5. Generate PDF → 6. Create ZIP

Frame extraction strategy (app/processor/video_utils.py `extract_frames`):
- If `frame_interval` > 0: capture frames every N seconds
- Default: PySceneDetect `ContentDetector` with configurable threshold
- Fallback: frame-by-interval if scene detection yields too few frames
- Max 50 frames (subsampled equidistantly if exceeded), min 10

### Key Config (.env)

| Variable | Purpose |
|----------|---------|
| `OPENAI_API_KEY` | API key for Whisper (OpenAI/Grok/DeepSeek/Ollama) |
| `OPENAI_BASE_URL` | Base URL for provider |
| `WHISPER_MODEL` | Model name (e.g., whisper-large-v3, whisper-1) |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token |
| `ALLOWED_USER_IDS` | Comma-separated Telegram user IDs (whitelist) |
| `SCENE_DETECT_THRESHOLD` | ContentDetector threshold (default 15.0) |
| `FRAME_INTERVAL_SECONDS` | Interval fallback (default 10) |

## Common Commands

```bash
# Build and start all services
docker-compose up --build

# View logs for all services
docker-compose logs -f

# View logs for a specific service
docker-compose logs -f celery-worker

# Rebuild a single service
docker-compose up --build -d api

# Run a Python one-liner inside a container
docker-compose exec api python -c "from app.database import SessionLocal; from app.models import Job; ..."
```

### Run locally (without Docker)

```bash
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your keys
redis-server
python -m app.main                  # API on :8000
celery -A app.celery_app worker --loglevel=info   # Worker
python run_bot.py                  # Telegram bot
python -m app.web.gradio_app       # Gradio on :7860
```

## Important Notes

- No test suite, linter, or formatter is configured
- The bot uses a `user_data_store` dict (in-memory) for conversation state — data is lost on restart
- Frame interval is persisted per-user in `data/user_intervals.json` (Telegram) and `data/gradio_frame_interval.json` (Gradio)
- SQLite runs in WAL mode for better concurrent reads/writes from multiple containers
- API security via `API_KEY` env var is optional (off by default)
- All services share mounted volumes: `./output`, `./temp`, `./logs`, `./db`
- Telegram notification uses raw `httpx` POST to Bot API (not python-telegram-bot)
- Video files are temporarily stored in `temp/` and cleaned up after processing

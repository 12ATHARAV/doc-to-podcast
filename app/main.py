"""Main FastAPI application entrypoint."""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi import Request
from loguru import logger

from app.config import settings
from app.api.routes import router as api_router
from app.api.websocket import manager


app = FastAPI(
    title="🎙️ Doc-to-Podcast",
    description="Transform any document into an engaging AI-powered podcast conversation",
    version="0.1.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API routes
app.include_router(api_router)

# Setup paths
import os
from pathlib import Path

STATIC_DIR = Path(__file__).parent.parent / "static"
TEMPLATES_DIR = Path(__file__).parent.parent / "app" / "templates"

# Ensure directories exist
STATIC_DIR.mkdir(parents=True, exist_ok=True)
(STATIC_DIR / "css").mkdir(parents=True, exist_ok=True)
(STATIC_DIR / "js").mkdir(parents=True, exist_ok=True)
TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)

# Mount static files
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Jinja2 templates
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@app.on_event("startup")
async def startup_event():
    """Startup tasks."""
    logger.info("Starting Doc-to-Podcast application...")
    
    # Dynamically inject ffmpeg into PATH for pydub
    try:
        import static_ffmpeg
        static_ffmpeg.add_paths()
        logger.info("FFmpeg paths dynamically added via static-ffmpeg.")
    except Exception as e:
        logger.warning(f"Could not initialize static-ffmpeg paths: {e}")

    settings.ensure_dirs()
    if not settings.gemini_api_key:
        logger.warning("GEMINI_API_KEY is not configured. Google Gemini LLM will not work.")
    if not settings.groq_api_key:
        logger.warning("GROQ_API_KEY is not configured. Groq fallback will not work.")


@app.get("/", response_class=HTMLResponse)
async def get_index(request: Request):
    """Serve the main index page."""
    index_path = TEMPLATES_DIR / "index.html"
    if index_path.exists():
        return templates.TemplateResponse(request=request, name="index.html")
    return HTMLResponse(
        content="<h2>🎙️ Doc-to-Podcast Backend is Running!</h2>"
                "<p>Please create and configure index.html in app/templates/ to see the frontend interface.</p>"
    )


@app.get("/status/{job_id}", response_class=HTMLResponse)
async def get_status_page(request: Request, job_id: str):
    """Serve the status page for a job."""
    status_path = TEMPLATES_DIR / "status.html"
    if status_path.exists():
        return templates.TemplateResponse(request=request, name="status.html", context={"job_id": job_id})
    return HTMLResponse(
        content=f"<h2>Job Status Tracking</h2>"
                f"<p>Job ID: <strong>{job_id}</strong></p>"
                f"<p>WebSocket progress updates available at: <code>/ws/progress/{job_id}</code></p>"
    )


@app.websocket("/ws/progress/{job_id}")
async def websocket_endpoint(websocket: WebSocket, job_id: str):
    """WebSocket endpoint for receiving live progress updates of a job."""
    await manager.connect(job_id, websocket)
    try:
        while True:
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(job_id, websocket)
    except Exception as e:
        logger.warning(f"WebSocket error for job {job_id}: {e}")
        manager.disconnect(job_id, websocket)


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "gemini_api_configured": bool(settings.gemini_api_key),
        "groq_api_configured": bool(settings.groq_api_key),
    }

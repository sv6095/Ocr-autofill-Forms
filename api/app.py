"""
FastAPI application setup and configuration.
"""
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path

from app.config import JWT_SECRET
from fastapi.staticfiles import StaticFiles

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# App instance MUST be named `app` for uvicorn import to succeed
app = FastAPI(
    title="OCR API",
    version="2.0.0",
    description="OCR backend with TrOCR, Tesseract, and MOSIP integration"
)

# CORS (adjust allowed_origins for production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://127.0.0.1:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import routes after app creation to avoid circular imports
from api.routes import router
from api.web_routes import router as web_router

# Include API routes
app.include_router(router, prefix="/api")

# Include web demo routes
app.include_router(web_router)

# Serve static files
BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "web" / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


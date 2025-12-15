# app/config.py
"""
Central configuration for the OCR backend.

This file merges your existing settings (upload paths, JWT, Tesseract, language map)
with service toggles and performance defaults used by the OCR pipeline.
Values are read from environment variables with sensible defaults so you can tune
behavior without changing code.
"""

import os
from pathlib import Path
from datetime import timedelta
from typing import Dict

# ---- base dirs ----
BASE_DIR = Path(__file__).resolve().parent.parent

STORAGE_DIR = BASE_DIR / "storage"
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

UPLOAD_DIR = STORAGE_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

CSV_EXPORT_DIR = BASE_DIR / "storage" / "csv_exports"
CSV_EXPORT_DIR.mkdir(parents=True, exist_ok=True)

# ---- external binary paths ----
# Poppler path - check common Windows installation locations
POPPLER_PATH = os.getenv("POPPLER_PATH", "")
if not POPPLER_PATH and os.name == 'nt':  # Windows
    # Check common Poppler installation paths
    common_paths = [
        r"C:\poppler\Library\bin",
        r"C:\Program Files\poppler\bin",
        r"C:\Program Files (x86)\poppler\bin",
        r"C:\tools\poppler\bin",
    ]
    for path in common_paths:
        if os.path.exists(path) and os.path.exists(os.path.join(path, "pdftoppm.exe")):
            POPPLER_PATH = path
            break

# Tesseract path - hardcoded for Windows installation
TESSERACT_CMD = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# ---- model registry / language mapping ----
# Models loaded directly from Hugging Face - no environment variables needed
DEFAULT_MODEL_REGISTRY: Dict[str, str] = {
    "eng": "microsoft/trocr-base-handwritten",  # Loaded directly from Hugging Face
}


# Map simple language codes to Tesseract traineddata codes (keeps your values)
TESSERACT_LANG_MAP: Dict[str, str] = {
    "hin": "hin",   # Hindi
    "tel": "tel",   # Telugu
    "tam": "tam",   # Tamil
    "mal": "mal",   # Malayalam
    "kan": "kan",   # Kannada
    "ara": "ara",   # Arabic
    "eng": "eng",
    "en": "eng",
}

# ---- auth / jwt ----
JWT_SECRET = os.getenv("JWT_SECRET", "change-me-in-prod")
JWT_ALGORITHM = "HS256"
JWT_EXP_DELTA = int(os.getenv("JWT_EXP_DELTA_SECONDS", "86400"))

# ---- feature toggles / booleans ----
# Note: TrOCR is now always used for English (printed/handwritten), Tesseract for other languages

# Handwriting pipeline: "auto" | "always" | "off"
HANDWRITING_PIPELINE = os.getenv("HANDWRITING_PIPELINE", "auto").lower()

# If full-page OCR result length < this (chars), handwriting pipeline triggers in "auto" mode
HANDWRITING_TRIGGER_MIN_CHARS = int(os.getenv("HANDWRITING_TRIGGER_MIN_CHARS", "40"))

# Max upload size allowed (bytes). Default 50 MB
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(50 * 1024 * 1024)))

# Debug: include intermediate images in response (local dev only)
DEBUG_INCLUDE_IMAGES = os.getenv("DEBUG_INCLUDE_IMAGES", "false").lower() in ("1", "true", "yes", "on")

# ---- performance / concurrency ----
# How many OCR requests can run concurrently (BoundedSemaphore). Keep low on CPU-only hosts.
OCR_MAX_CONCURRENT = int(os.getenv("OCR_MAX_CONCURRENT", "2"))

# Thread pool workers used to process pages (per-request page-level concurrency).
OCR_THREADPOOL_WORKERS = int(os.getenv("OCR_THREADPOOL_WORKERS", "2"))

# Default maximum page side (px) used for image resizing (speed/quality tradeoff).
DEFAULT_MAX_DIM = int(os.getenv("DEFAULT_MAX_DIM", "1200"))

# Default upscale factor for per-line crops (used by handwriting pipeline)
DEFAULT_UPSCALE_FACTOR = float(os.getenv("DEFAULT_UPSCALE_FACTOR", "1.8"))

# Transformers offline mode: Set to True to use cached models only (no internet required)
# Can also be set via environment variable: export TRANSFORMERS_OFFLINE=1
TRANSFORMERS_OFFLINE = os.getenv("TRANSFORMERS_OFFLINE", "0").lower() in ("1", "true", "yes", "on")

# ---- db / misc ----
# Directory to store uploads (already defined)
# UPLOAD_DIR above

# Database removed - no longer used
# DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'ocr.db'}")

# Local dev convenience: small sample image path (optional)
SAMPLE_IMAGE_PATH = os.getenv("SAMPLE_IMAGE_PATH", "")

# ---- expose items ----
__all__ = [
    "BASE_DIR",
    "STORAGE_DIR",
    "UPLOAD_DIR",
    "CSV_EXPORT_DIR",
    "POPPLER_PATH",
    "TESSERACT_CMD",
    "DEFAULT_MODEL_REGISTRY",
    "TESSERACT_LANG_MAP",
    "JWT_SECRET",
    "JWT_ALGORITHM",
    "JWT_EXP_DELTA",
    "HANDWRITING_PIPELINE",
    "HANDWRITING_TRIGGER_MIN_CHARS",
    "MAX_UPLOAD_BYTES",
    "DEBUG_INCLUDE_IMAGES",
    "OCR_MAX_CONCURRENT",
    "OCR_THREADPOOL_WORKERS",
    "DEFAULT_MAX_DIM",
    "DEFAULT_UPSCALE_FACTOR",
    "TRANSFORMERS_OFFLINE",
    "SAMPLE_IMAGE_PATH",
]

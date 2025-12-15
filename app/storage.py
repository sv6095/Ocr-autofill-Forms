# app/storage.py
from pathlib import Path
from uuid import uuid4
from .config import UPLOAD_DIR

def save_uploaded_file(file_bytes: bytes, original_filename: str) -> str:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    safe = original_filename.replace(" ", "_")
    unique = f"{uuid4().hex}_{safe}"
    path = UPLOAD_DIR / unique
    with open(path, "wb") as f:
        f.write(file_bytes)
    return str(path.resolve())

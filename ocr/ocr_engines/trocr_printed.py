"""
TrOCR model for printed text recognition.
Uses microsoft/trocr-small-printed for printed documents.
Loaded directly from Hugging Face.
"""
from typing import Optional
from PIL import Image
import os
import logging

from app.config import TRANSFORMERS_OFFLINE

logger = logging.getLogger(__name__)

# Optional TrOCR - wrap torch import in try-except
HAS_TROCR = False
try:
    import torch
    from transformers import TrOCRProcessor, VisionEncoderDecoderModel
    HAS_TROCR = True
except Exception:
    HAS_TROCR = False
    torch = None  # Set to None if not available

_trocr_printed_cache = None
_trocr_printed_device = None

# Load directly from Hugging Face - no environment variables needed
MODEL_NAME = "microsoft/trocr-small-printed"


def _load_trocr_printed():
    """Load TrOCR base model for printed text."""
    global _trocr_printed_cache, _trocr_printed_device
    
    if _trocr_printed_cache:
        return _trocr_printed_cache
    
    if not HAS_TROCR or torch is None:
        return None
    
    offline_mode = TRANSFORMERS_OFFLINE or os.getenv("TRANSFORMERS_OFFLINE", "0") == "1"
    _trocr_printed_device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    
    if offline_mode:
        logger.info(f"Loading TrOCR printed model '{MODEL_NAME}' in OFFLINE mode on device: {_trocr_printed_device}")
    else:
        logger.info(f"Loading TrOCR printed model '{MODEL_NAME}' on device: {_trocr_printed_device}")
    
    try:
        # Use local_files_only=True for offline mode
        processor = TrOCRProcessor.from_pretrained(
            MODEL_NAME,
            local_files_only=offline_mode
        )
        model = VisionEncoderDecoderModel.from_pretrained(
            MODEL_NAME,
            local_files_only=offline_mode
        ).to(_trocr_printed_device)
        model.eval()
        
        _trocr_printed_cache = {"proc": processor, "model": model}
        logger.info("TrOCR printed model loaded and cached successfully")
        return _trocr_printed_cache
    except Exception as e:
        if offline_mode:
            logger.error(f"Failed to load TrOCR printed model '{MODEL_NAME}' in offline mode. Make sure models are cached locally: {e}", exc_info=True)
        else:
            logger.error(f"Failed to load TrOCR printed model '{MODEL_NAME}': {e}", exc_info=True)
        return None


def ocr_printed_text(image: Image.Image, max_length: int = 256) -> str:
    """
    Perform OCR on printed text using TrOCR base model.
    
    Args:
        image: PIL Image (RGB)
        max_length: Maximum sequence length for generation
    
    Returns:
        Extracted text string
    """
    if not HAS_TROCR or torch is None:
        return ""
    
    try:
        cache = _load_trocr_printed()
        if not cache:
            return ""
        
        proc = cache["proc"]
        model = cache["model"]
        
        img = image.convert("RGB")
        encoded = proc(img, return_tensors="pt")
        pixel_values = encoded.pixel_values.to(_trocr_printed_device)
        
        with torch.no_grad():
            ids = model.generate(pixel_values, max_length=max_length)
        
        return proc.batch_decode(ids, skip_special_tokens=True)[0]
    except Exception:
        return ""


def is_available() -> bool:
    """Check if TrOCR printed model is available."""
    return HAS_TROCR


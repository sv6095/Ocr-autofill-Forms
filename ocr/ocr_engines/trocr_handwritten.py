"""
TrOCR model for handwriting recognition.
Uses microsoft/trocr-base-handwritten for handwritten text.
Loaded directly from Hugging Face.
"""
from typing import Dict, List, Tuple, Optional
from PIL import Image, ImageEnhance
import numpy as np
import cv2
import pytesseract
import os
import logging

from app.config import DEFAULT_UPSCALE_FACTOR, TESSERACT_CMD, TRANSFORMERS_OFFLINE

logger = logging.getLogger(__name__)

# Configure tesseract - use hardcoded path from config
pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD

# Optional TrOCR
HAS_TROCR = False
try:
    import torch
    from transformers import TrOCRProcessor, VisionEncoderDecoderModel
    HAS_TROCR = True
    logger.info("TrOCR libraries imported successfully")
except Exception as e:
    HAS_TROCR = False
    logger.warning(f"TrOCR libraries not available: {e}")

_trocr_handwritten_cache = None
_trocr_handwritten_device = None

# Load directly from Hugging Face - no environment variables needed
MODEL_NAME = "microsoft/trocr-base-handwritten"


def _load_trocr_handwritten():
    """Load TrOCR model for handwriting."""
    global _trocr_handwritten_cache, _trocr_handwritten_device
    
    if _trocr_handwritten_cache:
        return _trocr_handwritten_cache
    
    if not HAS_TROCR:
        logger.warning("TrOCR not available - libraries not imported")
        return None
    
    _trocr_handwritten_device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    offline_mode = TRANSFORMERS_OFFLINE or os.getenv("TRANSFORMERS_OFFLINE", "0") == "1"
    
    if offline_mode:
        logger.info(f"Loading TrOCR model '{MODEL_NAME}' in OFFLINE mode on device: {_trocr_handwritten_device}")
    else:
        logger.info(f"Loading TrOCR model '{MODEL_NAME}' on device: {_trocr_handwritten_device}")
    
    try:
        # Use local_files_only=True for offline mode
        processor = TrOCRProcessor.from_pretrained(
            MODEL_NAME,
            local_files_only=offline_mode
        )
        logger.debug("TrOCR processor loaded successfully")
        model = VisionEncoderDecoderModel.from_pretrained(
            MODEL_NAME,
            local_files_only=offline_mode
        ).to(_trocr_handwritten_device)
        model.eval()
        _trocr_handwritten_cache = {"proc": processor, "model": model}
        logger.info("TrOCR model loaded and cached successfully")
    except Exception as e:
        if offline_mode:
            logger.error(f"Failed to load TrOCR model '{MODEL_NAME}' in offline mode. Make sure models are cached locally: {e}", exc_info=True)
        else:
            logger.error(f"Failed to load TrOCR model '{MODEL_NAME}': {e}", exc_info=True)
        return None
    
    return _trocr_handwritten_cache


def _trocr_handwritten(image: Image.Image, max_length: int = 128) -> str:
    """Run TrOCR on a single image."""
    cache = _load_trocr_handwritten()
    if not cache:
        logger.debug("TrOCR cache not available, returning empty string")
        return ""
    
    try:
        proc = cache["proc"]
        model = cache["model"]
        
        img = image.convert("RGB")
        logger.debug(f"Processing image with TrOCR: size={img.size}, mode={img.mode}")
        
        encoded = proc(img, return_tensors="pt")
        pixel_values = encoded.pixel_values.to(_trocr_handwritten_device)
        
        with torch.no_grad():
            ids = model.generate(
                pixel_values, 
                max_length=max_length,
                num_beams=5,
                early_stopping=True
            )
        
        decoded_text = proc.batch_decode(ids, skip_special_tokens=True)[0]
        logger.debug(f"TrOCR decoded text: '{decoded_text[:50]}...' (length: {len(decoded_text)})")
        return decoded_text
    except Exception as e:
        logger.error(f"TrOCR processing failed: {e}", exc_info=True)
        return ""


def enhance(img: Image.Image) -> Image.Image:
    """Enhance image for handwriting recognition."""
    img = img.convert("RGB")
    img = ImageEnhance.Contrast(img).enhance(1.4)
    img = ImageEnhance.Sharpness(img).enhance(1.4)
    return img


def segment_lines(pil: Image.Image) -> List[Tuple[int, int]]:
    """
    Segment text lines using projection histogram.
    Returns list of (y1, y2) pairs for each text line.
    """
    gray = cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2GRAY)
    thr = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C,
        cv2.THRESH_BINARY_INV, 31, 15
    )
    
    # Dilate to connect characters of the same line
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (50, 3))
    dilated = cv2.dilate(thr, kernel, iterations=1)
    
    # Sum of pixels per row → projection profile
    proj = np.sum(dilated, axis=1)
    
    lines = []
    in_line = False
    start = 0
    
    for i, val in enumerate(proj):
        if val > 50 and not in_line:
            in_line = True
            start = i
        elif val < 50 and in_line:
            in_line = False
            end = i
            if end - start > 12:  # avoid tiny noise
                lines.append((start, end))
    
    return lines


def ocr_handwriting_page(
    image: Image.Image,
    use_trocr_if_available: bool = True,
    upscale_factor: float = DEFAULT_UPSCALE_FACTOR,
    tess_psm_for_line: int = 7
) -> Dict:
    """
    Perform OCR on handwriting by segmenting into lines.
    Always uses TrOCR for handwriting if available, falls back to Tesseract only if TrOCR is unavailable.
    
    Args:
        image: PIL Image (RGB)
        use_trocr_if_available: Use TrOCR if available (default: True)
        upscale_factor: Factor to upscale line crops
        tess_psm_for_line: Tesseract PSM mode for line OCR (fallback only)
    
    Returns:
        Dictionary with:
            - full_text: Complete extracted text
            - lines: List of line dictionaries with y1, y2, text, ocr_source
            - detected_rows: List of (y1, y2) tuples
    """
    img = enhance(image)
    lines_y = segment_lines(img)
    
    output_lines = []
    full_text = []
    
    for (y1, y2) in lines_y:
        crop = img.crop((0, y1 - 5, img.width, y2 + 5))
        
        # Upscale
        w, h = crop.size
        crop = crop.resize(
            (int(w * upscale_factor), int(h * upscale_factor)),
            Image.BICUBIC
        )
        
        # OCR - Try TrOCR first if available and requested
        text = ""
        source = "tesseract"
        
        if use_trocr_if_available and HAS_TROCR:
            try:
                trocr_text = _trocr_handwritten(crop)
                if trocr_text and trocr_text.strip():
                    text = trocr_text
                    source = "trocr"
                    logger.debug(f"TrOCR succeeded for line {y1}-{y2}: '{text[:30]}...'")
                else:
                    logger.debug(f"TrOCR returned empty text for line {y1}-{y2}, falling back to Tesseract")
            except Exception as e:
                logger.warning(f"TrOCR failed for line {y1}-{y2}: {e}, falling back to Tesseract")
                pass
        
        # Fallback to Tesseract if TrOCR not available, not requested, or failed
        if not text.strip():
            try:
                tesseract_text = pytesseract.image_to_string(crop, config=f"--psm {tess_psm_for_line}")
                if tesseract_text and tesseract_text.strip():
                    text = tesseract_text
                    source = "tesseract"
            except Exception:
                pass
        
        text = text.strip()
        if text:
            full_text.append(text)
        
        output_lines.append({
            "y1": int(y1),
            "y2": int(y2),
            "text": text,
            "ocr_source": source
        })
    
    return {
        "full_text": "\n".join(full_text),
        "lines": output_lines,
        "detected_rows": lines_y
    }


def is_available() -> bool:
    """Check if TrOCR handwritten model is available."""
    if not HAS_TROCR:
        return False
    # Try to load the model to verify it's actually available
    cache = _load_trocr_handwritten()
    is_avail = cache is not None
    if not is_avail:
        logger.warning("TrOCR libraries available but model failed to load")
    return is_avail


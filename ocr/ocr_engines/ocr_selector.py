"""
Auto-select best OCR engine based on image characteristics and text type.
"""
from typing import Dict, Optional, Tuple
from PIL import Image
import logging

from ocr.preprocessing.detector import detect_text_type, TextType
from ocr.ocr_engines.trocr_printed import ocr_printed_text, is_available as trocr_printed_available, HAS_TROCR as TROCR_PRINTED_IMPORTED
from ocr.ocr_engines.trocr_handwritten import ocr_handwriting_page, is_available as trocr_handwritten_available, HAS_TROCR as TROCR_HANDWRITTEN_IMPORTED
from ocr.ocr_engines.tesseract_multi import ocr_multilingual, ocr_with_confidence
from app.config import HANDWRITING_PIPELINE, HANDWRITING_TRIGGER_MIN_CHARS

logger = logging.getLogger(__name__)


class OCRResult:
    """OCR result container."""
    def __init__(
        self,
        text: str,
        engine: str,
        confidence: float = 0.0,
        metadata: Optional[Dict] = None
    ):
        self.text = text
        self.engine = engine
        self.confidence = confidence
        self.metadata = metadata or {}


def select_ocr_engine(
    image: Image.Image,
    language: str = "eng",
    text_type_hint: Optional[TextType] = None,
    force_engine: Optional[str] = None
) -> str:
    """
    Select the best OCR engine for the given image.
    ALWAYS uses TrOCR for English, Tesseract for other languages.
    
    Args:
        image: PIL Image
        language: Language code
        text_type_hint: Hint about text type (printed/handwritten) - used to choose TrOCR variant
        force_engine: Force specific engine ("trocr_printed", "trocr_handwritten", "tesseract")
    
    Returns:
        Engine name: "trocr_printed", "trocr_handwritten", or "tesseract"
    """
    if force_engine:
        logger.debug(f"Forcing OCR engine: {force_engine}")
        return force_engine
    
    # For non-English languages, ALWAYS use Tesseract
    if language != "eng":
        logger.info(f"Non-English language ({language}) - using Tesseract")
        return "tesseract"
    
    # For English, ALWAYS use TrOCR
    # Try to detect text type to choose between printed/handwritten TrOCR models
    if text_type_hint is None:
        try:
            text_type_hint = detect_text_type(image)
            logger.debug(f"Auto-detected text type: {text_type_hint}")
        except Exception as e:
            logger.warning(f"Text type detection failed: {e}, defaulting to handwritten TrOCR")
            text_type_hint = TextType.UNKNOWN
    
    # For English, ALWAYS use TrOCR
    # Prefer handwritten TrOCR for handwritten or mixed text (handwritten handles both better)
    if text_type_hint in (TextType.HANDWRITTEN, TextType.MIXED):
        if TROCR_HANDWRITTEN_IMPORTED:
            logger.info(f"English text ({text_type_hint.value}) - using TrOCR handwritten model")
            return "trocr_handwritten"
        elif TROCR_PRINTED_IMPORTED:
            logger.warning(f"TrOCR handwritten not available, using printed model for {text_type_hint.value} text")
            return "trocr_printed"
    
    # For printed or unknown text, prefer printed TrOCR
    if text_type_hint == TextType.PRINTED:
        if TROCR_PRINTED_IMPORTED:
            logger.info("English text (printed) - using TrOCR printed model")
            return "trocr_printed"
        elif TROCR_HANDWRITTEN_IMPORTED:
            logger.warning("TrOCR printed not available, using handwritten model for printed text")
            return "trocr_handwritten"
    
    # For unknown text type, prefer handwritten TrOCR (more flexible)
    if text_type_hint == TextType.UNKNOWN:
        if TROCR_HANDWRITTEN_IMPORTED:
            logger.info("English text (unknown type) - using TrOCR handwritten model")
            return "trocr_handwritten"
        elif TROCR_PRINTED_IMPORTED:
            logger.info("English text (unknown type) - using TrOCR printed model (fallback)")
            return "trocr_printed"
    
    # Final fallback - try any available TrOCR
    if TROCR_HANDWRITTEN_IMPORTED:
        logger.info("English text - using TrOCR handwritten model (final fallback)")
        return "trocr_handwritten"
    elif TROCR_PRINTED_IMPORTED:
        logger.info("English text - using TrOCR printed model (final fallback)")
        return "trocr_printed"
    
    # Final fallback to Tesseract if TrOCR not available at all
    logger.warning("English text but TrOCR not available - falling back to Tesseract")
    return "tesseract"


def perform_ocr(
    image: Image.Image,
    language: str = "eng",
    text_type_hint: Optional[TextType] = None,
    force_engine: Optional[str] = None,
    use_multistage: bool = True
) -> OCRResult:
    """
    Perform OCR using the best available engine.
    
    Args:
        image: PIL Image
        language: Language code
        text_type_hint: Hint about text type
        force_engine: Force specific engine
        use_multistage: Use multi-stage OCR (try multiple engines)
    
    Returns:
        OCRResult with text, engine name, and metadata
    """
    engine = select_ocr_engine(image, language, text_type_hint, force_engine)
    
    # Primary OCR
    if engine == "trocr_printed":
        text = ocr_printed_text(image)
        confidence = 0.85  # TrOCR doesn't provide confidence scores
        metadata = {
            "engine": "trocr_printed",
            "model": "microsoft/trocr-small-printed"  # Loaded directly from Hugging Face
        }
    elif engine == "trocr_handwritten":
        logger.info("Using TrOCR for handwriting recognition")
        try:
            result = ocr_handwriting_page(image, use_trocr_if_available=True)
            text = result.get("full_text", "")
            lines = result.get("lines", [])
            # Check which OCR source was actually used
            trocr_lines = [line for line in lines if line.get("ocr_source") == "trocr"]
            tesseract_lines = [line for line in lines if line.get("ocr_source") == "tesseract"]
            if trocr_lines:
                logger.info(f"TrOCR successfully processed {len(trocr_lines)} lines")
            if tesseract_lines:
                logger.warning(f"TrOCR fell back to Tesseract for {len(tesseract_lines)} lines")
            confidence = 0.80
            metadata = {
                "engine": "trocr_handwritten",
                "lines": lines,
                "trocr_lines_count": len(trocr_lines),
                "tesseract_lines_count": len(tesseract_lines),
                "model": "microsoft/trocr-base-handwritten"  # Loaded directly from Hugging Face
            }
        except Exception as e:
            logger.error(f"TrOCR handwriting processing failed: {e}", exc_info=True)
            # Fallback to Tesseract
            text, confidence = ocr_with_confidence(image, language, psm=3)
            metadata = {
                "engine": "tesseract",
                "language": language,
                "confidence": confidence,
                "trocr_failed": True,
                "trocr_error": str(e)
            }
    else:  # tesseract
        text, confidence = ocr_with_confidence(image, language, psm=3)
        metadata = {"engine": "tesseract", "language": language, "confidence": confidence}
    
    # Multi-stage: if result is poor and we have alternatives, try them
    if use_multistage and len(text.strip()) < HANDWRITING_TRIGGER_MIN_CHARS:
        if engine != "trocr_handwritten" and trocr_handwritten_available() and HANDWRITING_PIPELINE != "off":
            try:
                hw_result = ocr_handwriting_page(image, use_trocr_if_available=True)
                hw_text = hw_result.get("full_text", "")
                if hw_text and len(hw_text.strip()) > len(text.strip()):
                    text = hw_text
                    engine = "trocr_handwritten"
                    confidence = 0.80
                    metadata.update({
                        "engine": "trocr_handwritten",
                        "fallback_used": True,
                        "lines": hw_result.get("lines", [])
                    })
            except Exception:
                pass
    
    return OCRResult(text=text, engine=engine, confidence=confidence, metadata=metadata)


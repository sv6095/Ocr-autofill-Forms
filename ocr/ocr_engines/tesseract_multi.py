"""
Tesseract OCR for multilingual support.
Supports multiple languages including Indian languages.
"""
from typing import Optional
from PIL import Image
import pytesseract

from app.config import TESSERACT_CMD, TESSERACT_LANG_MAP

# Configure tesseract - use hardcoded path from config
pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD


def get_tesseract_lang(language: str) -> str:
    """
    Map language code to Tesseract language code.
    
    Args:
        language: Language code (eng, hin, tel, etc.)
    
    Returns:
        Tesseract language code
    """
    return TESSERACT_LANG_MAP.get(language.lower(), "eng")


def ocr_multilingual(
    image: Image.Image,
    language: str = "eng",
    psm: int = 3,
    config: Optional[str] = None
) -> str:
    """
    Perform OCR using Tesseract with multilingual support.
    
    Args:
        image: PIL Image
        language: Language code (eng, hin, tel, tam, mal, kan, ara, etc.)
        psm: Page segmentation mode (0-13)
        config: Additional Tesseract config string
    
    Returns:
        Extracted text string
    """
    tess_lang = get_tesseract_lang(language)
    
    if config:
        full_config = f"--psm {psm} {config}"
    else:
        full_config = f"--psm {psm}"
    
    try:
        return pytesseract.image_to_string(image, lang=tess_lang, config=full_config)
    except Exception as e:
        # Fallback to English if language not available
        try:
            return pytesseract.image_to_string(image, lang="eng", config=full_config)
        except Exception:
            return ""


def ocr_with_confidence(
    image: Image.Image,
    language: str = "eng",
    psm: int = 3
) -> tuple[str, float]:
    """
    Perform OCR and return text with confidence score.
    
    Args:
        image: PIL Image
        language: Language code
        psm: Page segmentation mode
    
    Returns:
        Tuple of (text, average_confidence)
    """
    tess_lang = get_tesseract_lang(language)
    config = f"--psm {psm}"
    
    try:
        data = pytesseract.image_to_data(image, lang=tess_lang, config=config, output_type=pytesseract.Output.DICT)
        text_parts = []
        confidences = []
        
        for i, conf in enumerate(data.get("conf", [])):
            if int(conf) > 0:
                text = data.get("text", [""])[i]
                if text.strip():
                    text_parts.append(text)
                    confidences.append(float(conf))
        
        text = " ".join(text_parts)
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
        
        return text, avg_confidence
    except Exception:
        text = ocr_multilingual(image, language, psm)
        return text, 0.0


def get_available_languages() -> list[str]:
    """
    Get list of available Tesseract languages.
    
    Returns:
        List of language codes
    """
    try:
        langs = pytesseract.get_languages()
        return langs
    except Exception:
        return ["eng"]


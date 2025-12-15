"""
Main extraction logic for OCR processing.
"""
import time
import concurrent.futures
import threading
from typing import Dict, Tuple, List
from io import BytesIO
from PIL import Image, UnidentifiedImageError

from app.pdf_utils import pdf_to_images
from app.image_processing import (
    preprocess_pipeline,
    open_image_bytes,
    upscale_region,
    sharpen_and_contrast,
    pil_to_cv,
    detect_small_text_regions,
    cv_to_pil
)
from app.config import (
    TESSERACT_LANG_MAP,
    OCR_MAX_CONCURRENT,
    OCR_THREADPOOL_WORKERS,
    HANDWRITING_PIPELINE,
    HANDWRITING_TRIGGER_MIN_CHARS,
    DEFAULT_MAX_DIM,
    DEFAULT_UPSCALE_FACTOR
)
from app.table_recognition import detect_tables, ocr_cells_on_table
from ocr.ocr_engines.ocr_selector import perform_ocr
from ocr.preprocessing.detector import detect_text_type
from ocr.extraction.field_mapper import map_fields_from_text
from app.config import TESSERACT_CMD
import pytesseract

# Configure tesseract - use hardcoded path from config
pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD

# Verify Tesseract is accessible
def _verify_tesseract():
    """Verify Tesseract is accessible and log version info."""
    import logging
    logger = logging.getLogger(__name__)
    try:
        version = pytesseract.get_tesseract_version()
        logger.info(f"Tesseract initialized successfully - Version: {version}, Path: {TESSERACT_CMD}")
        return True
    except Exception as e:
        logger.error(f"Tesseract verification failed: {e}. Path: {TESSERACT_CMD}")
        return False

# Verify on module load (non-blocking - just logs warning if fails)
try:
    _verify_tesseract()
except Exception as e:
    import logging
    logger = logging.getLogger(__name__)
    logger.warning(f"Tesseract verification error during module load: {e}. Continuing anyway.")

# Concurrency controls
_GLOBAL_SEMAPHORE = threading.BoundedSemaphore(
    OCR_MAX_CONCURRENT if OCR_MAX_CONCURRENT and OCR_MAX_CONCURRENT > 0 else 1
)
_EXECUTOR = concurrent.futures.ThreadPoolExecutor(
    max_workers=OCR_THREADPOOL_WORKERS if OCR_THREADPOOL_WORKERS > 0 else 1
)


def _tesseract_ocr_on_image(image: Image.Image, lang_code: str, psm: int = 3) -> str:
    """Run Tesseract OCR on image with proper error handling."""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        config = f"--psm {psm}"
        text = pytesseract.image_to_string(image, lang=lang_code, config=config)
        logger.debug(f"Tesseract OCR successful: {len(text)} characters (lang: {lang_code}, psm: {psm})")
        return text
    except Exception as e:
        logger.warning(f"Tesseract OCR with language '{lang_code}' failed: {e}, trying without language")
        try:
            text = pytesseract.image_to_string(image, config=f"--psm {psm}")
            logger.debug(f"Tesseract OCR fallback successful: {len(text)} characters")
            return text
        except Exception as e2:
            logger.error(f"Tesseract OCR completely failed: {e2}")
            return ""


def _extract_key_value_fields(raw_text: str) -> Dict[str, str]:
    """Extract key-value pairs from raw text using template matching."""
    import logging
    logger = logging.getLogger(__name__)
    logger.debug(f"_extract_key_value_fields: raw_text length = {len(raw_text) if raw_text else 0}")
    if raw_text:
        logger.debug(f"_extract_key_value_fields: raw_text preview (first 500 chars):\n{raw_text[:500]}")
    fields, field_confidences = map_fields_from_text(raw_text, use_template_matching=True, partial=True)
    logger.debug(f"_extract_key_value_fields: extracted {len(fields)} fields: {list(fields.keys())}")
    return fields, field_confidences


def perform_extraction(
    file_bytes: bytes,
    filename: str,
    content_type: str,
    language: str = "eng",
    run_table_ocr: bool = True,
    enable_multistage: bool = True,
    handwriting_mode: str = "auto"
) -> Tuple[str, Dict[str, str], Dict[str, float], int, List]:
    """
    Perform OCR extraction on document.
    
    Args:
        file_bytes: Document file bytes
        filename: Original filename
        content_type: MIME type
        language: Language code
        run_table_ocr: Whether to detect and OCR tables
        enable_multistage: Enable multi-stage OCR
        handwriting_mode: Handwriting detection mode
    
    Returns:
        Tuple of (raw_text, fields_dict, pages_count, tables_list)
    """
    # Acquire semaphore to avoid too many concurrent heavy requests
    acquired = _GLOBAL_SEMAPHORE.acquire(timeout=60)
    if not acquired:
        raise RuntimeError("Server busy. Try again later.")

    try:
        import logging
        logger = logging.getLogger(__name__)
        
        tstart = time.time()
        fname = (filename or "").lower()
        ctype = (content_type or "").lower()
        header = file_bytes[:8] if file_bytes else b""
        
        # Better file type detection
        is_pdf = (
            fname.endswith(".pdf") or 
            "pdf" in ctype or 
            header.startswith(b"%PDF") or
            header.startswith(b"%PDF-")
        )
        
        # Detect image types
        is_image = False
        image_format = None
        if header.startswith(b'\x89PNG'):
            is_image = True
            image_format = 'PNG'
        elif header.startswith(b'\xff\xd8\xff'):
            is_image = True
            image_format = 'JPEG'
        elif header.startswith(b'GIF'):
            is_image = True
            image_format = 'GIF'
        elif header.startswith(b'BM'):
            is_image = True
            image_format = 'BMP'
        elif fname.endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff', '.tif', '.webp')):
            is_image = True
            image_format = fname.split('.')[-1].upper()
        
        logger.info(f"File type detection - filename: {filename}, content_type: {content_type}, is_pdf: {is_pdf}, is_image: {is_image}, format: {image_format}")
        
        if not is_pdf and not is_image:
            raise RuntimeError(f"Unsupported file type. Expected PDF or image (PNG, JPEG, etc.), got: {filename or 'unknown'}")

        pages_count = 0
        all_text_parts: List[str] = []
        detected_tables_all: List[Dict] = []
        lang = (language or "eng").lower()
        # TrOCR is now always used for English (printed/handwritten), Tesseract for other languages

        def process_single_image(img: Image.Image, page_idx: int) -> str:
            """Process a single image page with proper OCR model selection."""
            import logging
            logger = logging.getLogger(__name__)
            logger.debug(f"Processing page {page_idx + 1}")
            
            p0 = time.time()
            # Preprocess
            pre = preprocess_pipeline(
                img,
                deskew=True,
                binarize=True,
                denoise_strength=6,
                dilate_iter=0,
                erode_iter=0,
                upscale_small_text=True,
                max_dim=DEFAULT_MAX_DIM
            )
            t1 = time.time()
            text_out = ""
            
            # Detect text type to choose appropriate OCR engine
            try:
                from ocr.preprocessing.detector import detect_text_type, TextType
                text_type = detect_text_type(pre)
                logger.debug(f"Page {page_idx + 1}: Detected text type: {text_type}")
            except Exception as e:
                logger.debug(f"Text type detection failed: {e}, defaulting to printed")
                text_type = None
            
            # Use OCR selector to choose the best engine
            try:
                from ocr.ocr_engines.ocr_selector import perform_ocr, select_ocr_engine
                
                # Select appropriate OCR engine
                selected_engine = select_ocr_engine(
                    pre,
                    language=lang,
                    text_type_hint=text_type,
                    force_engine=None
                )
                logger.debug(f"Page {page_idx + 1}: Selected OCR engine: {selected_engine}")
                
                # Perform OCR using selected engine
                ocr_result = perform_ocr(
                    pre,
                    language=lang,
                    text_type_hint=text_type,
                    force_engine=None,
                    use_multistage=enable_multistage
                )
                
                if ocr_result and ocr_result.text:
                    text_out = ocr_result.text
                    logger.debug(f"Page {page_idx + 1}: OCR extracted {len(text_out)} characters using {selected_engine}")
                else:
                    logger.warning(f"Page {page_idx + 1}: OCR returned empty text")
                    
            except Exception as e:
                import traceback
                logger.error(f"OCR selector failed: {e}\n{traceback.format_exc()}")
                # Fallback logic: For English, try TrOCR directly; for other languages, use Tesseract
                text_out = ""
                try:
                    if lang == "eng":
                        # For English, try TrOCR handwritten as fallback
                        logger.warning("OCR selector failed for English - trying TrOCR handwritten directly")
                        from ocr.ocr_engines.trocr_handwritten import ocr_handwriting_page
                        hw_result = ocr_handwriting_page(pre, use_trocr_if_available=True)
                        text_out = hw_result.get("full_text", "") if isinstance(hw_result, dict) else (hw_result or "")
                        if not text_out:
                            # If TrOCR handwritten fails, try printed
                            logger.warning("TrOCR handwritten failed - trying TrOCR printed")
                            from ocr.ocr_engines.trocr_printed import ocr_printed_text
                            text_out = ocr_printed_text(pre)
                        if not text_out:
                            logger.warning("All TrOCR models failed - falling back to Tesseract for English")
                            tess_lang = TESSERACT_LANG_MAP.get(lang, "eng")
                            text_out = _tesseract_ocr_on_image(pre, tess_lang, psm=3)
                    else:
                        # For non-English, use Tesseract
                        logger.warning(f"OCR selector failed for {lang} - using Tesseract fallback")
                        tess_lang = TESSERACT_LANG_MAP.get(lang, "eng")
                        text_out = _tesseract_ocr_on_image(pre, tess_lang, psm=3)
                    logger.debug(f"Page {page_idx + 1}: Fallback OCR extracted {len(text_out)} characters")
                except Exception as e2:
                    logger.error(f"Fallback OCR also failed: {e2}\n{traceback.format_exc()}")
                    text_out = ""
            
            t2 = time.time()

            # If text is poor -> run handwriting helper
            should_hw = False
            if handwriting_mode == "always":
                should_hw = True
            elif handwriting_mode == "auto":
                if not text_out or len(text_out.strip()) < HANDWRITING_TRIGGER_MIN_CHARS:
                    should_hw = True

            if should_hw:
                try:
                    from ocr.ocr_engines.trocr_handwritten import ocr_handwriting_page
                    # Always use TrOCR for handwriting
                    hw_result = ocr_handwriting_page(
                        pre,
                        use_trocr_if_available=True,
                        tess_psm_for_line=7,
                        upscale_factor=DEFAULT_UPSCALE_FACTOR
                    )
                    hw_text = hw_result.get("full_text", "") if isinstance(hw_result, dict) else (hw_result or "")
                    if hw_text and len(hw_text.strip()) > len(text_out.strip()):
                        text_out = hw_text
                except Exception:
                    pass
            t3 = time.time()

            # Optional small-region pass to catch tiny cells
            try:
                cv_img = pil_to_cv(pre)
                boxes = detect_small_text_regions(cv_img)
                if boxes:
                    pil_pre = pre.convert("RGB")
                    for (x, y, w, h) in boxes:
                        try:
                            crop = pil_pre.crop((x, y, x + w, y + h))
                            up = upscale_region(crop, scale=1.8)
                            up = sharpen_and_contrast(up, sharpness=1.4, contrast=1.05)
                            tiny_text = _tesseract_ocr_on_image(up, TESSERACT_LANG_MAP.get(lang, "eng"), psm=6)
                            if tiny_text and len(tiny_text.strip()) > 1:
                                text_out += "\n" + tiny_text
                        except Exception:
                            continue
            except Exception:
                pass
            t4 = time.time()

            # Table detection
            if run_table_ocr:
                try:
                    tables = detect_tables(pre)
                    for tbl in tables:
                        tbl_cells = ocr_cells_on_table(pre, tbl["cells"], tess_lang=TESSERACT_LANG_MAP.get(lang, "eng"))
                        tbl["cells"] = tbl_cells
                    if tables:
                        detected_tables_all.append({"page": page_idx, "tables": tables})
                except Exception:
                    pass
            p1 = time.time()
            return text_out

        # Gather images with proper error handling
        images = []
        try:
            if is_pdf:
                logger.info("Processing PDF file")
                try:
                    images = pdf_to_images(file_bytes)
                    logger.info(f"PDF converted to {len(images)} page(s)")
                except RuntimeError as pdf_err:
                    if "poppler" in str(pdf_err).lower() or "POPPLER" in str(pdf_err):
                        error_msg = (
                            f"PDF processing requires Poppler to be installed.\n\n"
                            f"{str(pdf_err)}\n\n"
                            f"Alternatively, you can convert your PDF to images (PNG/JPEG) and upload those instead."
                        )
                        logger.error(error_msg)
                        raise RuntimeError(error_msg) from pdf_err
                    raise
            else:
                logger.info(f"Processing image file (format: {image_format})")
                try:
                    pil = Image.open(BytesIO(file_bytes))
                    # Handle multi-page images (TIFF, GIF animations, etc.)
                    i = 0
                    while True:
                        try:
                            pil.seek(i)
                            images.append(pil.convert("RGB"))
                            i += 1
                        except EOFError:
                            break
                    # If no frames found, use the single image
                    if not images:
                        images = [pil.convert("RGB")]
                except UnidentifiedImageError:
                    logger.warning("PIL couldn't identify image, trying open_image_bytes")
                    pil = open_image_bytes(file_bytes)
                    images = [pil.convert("RGB")]
                except Exception as e:
                    logger.error(f"Failed to open image: {e}")
                    raise RuntimeError(f"Failed to open image file: {e}")
            
            if not images:
                raise RuntimeError("No images found in uploaded file")
            
            pages_count = len(images)
            logger.info(f"Successfully loaded {pages_count} page(s) for OCR processing")
            
        except Exception as e:
            logger.error(f"Error loading file: {e}")
            raise RuntimeError(f"Failed to process file: {e}")

        # Process pages with limited threadpool concurrency
        logger.info(f"Starting OCR processing on {pages_count} page(s) using language: {lang}")
        futures = []
        for idx, img in enumerate(images):
            futures.append(_EXECUTOR.submit(process_single_image, img, idx))
        
        for fut in concurrent.futures.as_completed(futures, timeout=300):
            try:
                page_text = fut.result()
                if page_text:
                    all_text_parts.append(page_text)
                    logger.debug(f"Page processed successfully: {len(page_text)} characters")
                else:
                    logger.warning("Page processed but returned empty text")
            except Exception as e:
                logger.error(f"Error processing page: {e}")
                all_text_parts.append("")
        
        raw_text = "\n\n".join([p for p in all_text_parts if p])
        logger.info(f"perform_extraction: Extracted {len(raw_text)} characters of text from {pages_count} pages")
        logger.debug(f"perform_extraction: Raw text preview:\n{raw_text[:1000] if raw_text else '(empty)'}")
        
        if not raw_text or len(raw_text.strip()) == 0:
            logger.warning("WARNING: No text extracted from document! OCR may have failed.")
        
        fields, field_confidences = _extract_key_value_fields(raw_text)
        logger.info(f"perform_extraction: Extracted {len(fields)} fields: {list(fields.keys())}")
        tend = time.time()
        return raw_text, fields, field_confidences, pages_count, detected_tables_all
    finally:
        try:
            _GLOBAL_SEMAPHORE.release()
        except Exception:
            pass


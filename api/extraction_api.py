"""
API 1: Text Extraction endpoint.
Handles document upload and OCR text extraction.
"""
import json
import traceback
from uuid import uuid4
from typing import Optional
from io import BytesIO
from pathlib import Path

from fastapi import File, UploadFile, Form, HTTPException, Depends
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials
from PIL import Image

from app.storage import save_uploaded_file
# Database removed - document storage disabled
# from app.crud import create_document
from app.schemas import ExtractResponse
from app.config import MAX_UPLOAD_BYTES, HANDWRITING_PIPELINE, HANDWRITING_TRIGGER_MIN_CHARS
from api.auth import auth_scheme
from app.security import decode_access_token
from ocr.extraction.extractor import perform_extraction
from ocr.extraction.field_mapper import get_available_fields


def get_current_user(creds: Optional[HTTPAuthorizationCredentials] = Depends(auth_scheme)):
    """Parse Authorization header and return current user. Database removed - just validates token."""
    if not creds or not creds.credentials:
        # For web demo, allow anonymous access
        # In production, you should require authentication
        return None
    try:
        token = creds.credentials
        payload = decode_access_token(token)
        if not payload or not payload.get("sub"):
            return None
        # Return a simple dict instead of User model since DB is removed
        return {"email": payload["sub"]}
    except Exception:
        return None


async def extract_text(
    file: UploadFile = File(...),
    language: str = Form("eng"),
    run_table_ocr: Optional[bool] = Form(True),
    enable_multistage: Optional[bool] = Form(True),
    handwriting_mode: Optional[str] = Form(None),  # "auto"|"always"|"off"
    current_user: Optional[dict] = Depends(get_current_user)
):
    """
    Extract text from uploaded document using OCR.
    
    Args:
        file: Uploaded document (image or PDF)
        language: Language code (eng, hin, tel, etc.)
        run_table_ocr: Whether to detect and OCR tables
        enable_multistage: Enable multi-stage OCR processing
        handwriting_mode: Handwriting detection mode
        current_user: Authenticated user (dict, database removed)
    
    Returns:
        JSONResponse with extracted text, fields, and metadata
    """
    try:
        file_bytes = await file.read()
        if not file_bytes:
            raise HTTPException(status_code=400, detail="Empty file")
        if MAX_UPLOAD_BYTES and len(file_bytes) > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"File too large ({len(file_bytes)} bytes)"
            )

        # Save file
        file_path = save_uploaded_file(file_bytes, file.filename or "upload")

        # Run OCR extraction
        raw_text, fields, field_confidences, pages, tables = perform_extraction(
            file_bytes=file_bytes,
            filename=file.filename or "file",
            content_type=file.content_type or "",
            language=language,
            run_table_ocr=bool(run_table_ocr),
            enable_multistage=bool(enable_multistage),
            handwriting_mode=handwriting_mode or HANDWRITING_PIPELINE
        )

        # Optionally run handwriting per-line helper if configured
        handwriting_lines = []
        used_handwriting = False
        effective_hw_mode = handwriting_mode or HANDWRITING_PIPELINE
        if effective_hw_mode not in ("auto", "always", "off"):
            effective_hw_mode = "auto"
        
        try:
            if effective_hw_mode == "always" or (
                effective_hw_mode == "auto" and 
                (not raw_text or len(raw_text.strip()) < HANDWRITING_TRIGGER_MIN_CHARS)
            ):
                from ocr.ocr_engines.trocr_handwritten import ocr_handwriting_page
                # Attempt to open image frames/pages
                try:
                    pil = Image.open(BytesIO(file_bytes))
                    images = []
                    try:
                        i = 0
                        while True:
                            pil.seek(i)
                            images.append(pil.convert("RGB"))
                            i += 1
                    except EOFError:
                        pass
                    if not images:
                        images = [pil.convert("RGB")]
                except Exception:
                    # Fallback: if it's PDF, reuse pdf_to_images
                    try:
                        from app.pdf_utils import pdf_to_images
                        images = pdf_to_images(file_bytes)
                    except Exception:
                        images = []

                for p in images:
                    try:
                        hw = ocr_handwriting_page(p, use_trocr_if_available=True)
                        if isinstance(hw, dict):
                            handwriting_lines.append(hw.get("lines", []))
                        used_handwriting = True
                    except Exception:
                        continue
        except Exception:
            # Don't fail on handwriting helper issues
            used_handwriting = False

        # Database removed - document not stored
        # doc_uuid = uuid4().hex
        # document = create_document(...)
        
        # Get available fields (for partial data mapping info)
        available_fields = get_available_fields(raw_text)
        
        # Ensure fields is a dict, not None
        if fields is None:
            fields = {}
        
        # Log for debugging
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Extraction response - fields: {len(fields)}, available_fields: {len(available_fields)}, raw_text length: {len(raw_text)}")
        logger.debug(f"Fields extracted: {list(fields.keys())}")
        logger.debug(f"Available fields: {list(available_fields)}")
        
        response = {
            "document_id": 0,  # No database ID
            "language": language,
            "pages": pages,
            "raw_text": raw_text or "",  # Ensure it's a string
            "fields": fields,  # Ensure it's a dict
            "field_confidences": field_confidences or {},  # Confidence scores for each field
            "available_fields": list(available_fields) if available_fields else [],  # Fields detected in document
            "tables": tables or [],
            "used_handwriting_pipeline": used_handwriting,
            "handwriting_lines": handwriting_lines or []
        }
        return JSONResponse(content=response)
    except HTTPException:
        raise
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        tb = traceback.format_exc()
        error_msg = f"OCR extraction failed: {str(e)}"
        logger.error(f"{error_msg}\n{tb}")
        # Always return detailed error for debugging
        raise HTTPException(
            status_code=500,
            detail=f"{error_msg}\n\nTraceback:\n{tb}"
        )


"""
API 2: Data Verification endpoint.
Compares extracted OCR data with submitted user data.
"""
import json
import traceback
from uuid import uuid4
from typing import Optional
from io import BytesIO

from fastapi import File, UploadFile, Form, HTTPException, Depends
from fastapi.security import HTTPAuthorizationCredentials
from PIL import Image

from app.storage import save_uploaded_file
# Database removed - document and verification storage disabled
# from app.crud import create_document, create_verification_session
from app.schemas import VerificationResponse
from app.config import MAX_UPLOAD_BYTES, HANDWRITING_PIPELINE, HANDWRITING_TRIGGER_MIN_CHARS
from api.auth import auth_scheme
from app.security import decode_access_token
from ocr.extraction.extractor import perform_extraction
from ocr.verification.comparator import verify_submitted_data


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


async def verify_data(
    file: UploadFile = File(...),
    fields_json: str = Form(...),
    language: str = Form("eng"),
    run_table_ocr: Optional[bool] = Form(True),
    handwriting_mode: Optional[str] = Form(None),  # "auto"|"always"|"off"
    current_user: Optional[dict] = Depends(get_current_user)
):
    """
    Verify submitted data against extracted OCR data.
    
    Args:
        file: Uploaded document (image or PDF)
        fields_json: JSON string with submitted field values
        language: Language code (eng, hin, tel, etc.)
        run_table_ocr: Whether to detect and OCR tables
        handwriting_mode: Handwriting detection mode
        current_user: Authenticated user (dict, database removed)
    
    Returns:
        VerificationResponse with comparison results
    """
    try:
        try:
            parsed = json.loads(fields_json)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="fields_json must be valid JSON")
        if not isinstance(parsed, dict):
            raise HTTPException(
                status_code=400,
                detail="fields_json must be a JSON object { field: value }"
            )
        submitted_data = {str(k): str(v) for k, v in parsed.items()}

        file_bytes = await file.read()
        if not file_bytes:
            raise HTTPException(status_code=400, detail="Empty file")
        if MAX_UPLOAD_BYTES and len(file_bytes) > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"File too large ({len(file_bytes)} bytes)"
            )

        # Save file
        file_path = save_uploaded_file(file_bytes, file.filename or "file")

        # Primary OCR pass
        raw_text, extracted_fields, field_confidences, pages, tables = perform_extraction(
            file_bytes=file_bytes,
            filename=file.filename or "file",
            content_type=file.content_type or "",
            language=language,
            run_table_ocr=bool(run_table_ocr),
            enable_multistage=True,
            handwriting_mode=handwriting_mode or HANDWRITING_PIPELINE
        )

        # Optionally run handwriting helper if raw_text is poor and config says so
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
            used_handwriting = False

        # Database removed - document and verification not stored
        # doc_uuid = uuid4().hex
        # document = create_document(...)
        
        # Run verification logic
        field_results_pydantic, overall_conf = verify_submitted_data(
            submitted_data=submitted_data,
            extracted_fields=extracted_fields
        )

        return VerificationResponse(
            document_id=0,  # No database ID
            verification_id=0,  # No database ID
            language=language,
            pages=pages,
            overall_confidence=overall_conf,
            field_results=field_results_pydantic,
            extracted_fields=extracted_fields,
            raw_text=raw_text,
            handwriting_lines=handwriting_lines if used_handwriting else None
        )
    except HTTPException:
        raise
    except Exception as e:
        tb = traceback.format_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Verification failed: {e}\n{tb}"
        )


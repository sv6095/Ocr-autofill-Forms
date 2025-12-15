"""
API routes configuration.
"""
from fastapi import APIRouter, File, UploadFile, Form, Depends, HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse, FileResponse
from typing import List, Optional
from pathlib import Path
from io import BytesIO
import json
import csv
import traceback
from datetime import datetime

from PIL import Image
import numpy as np
import cv2
from app.schemas import (
    ExtractResponse,
    VerificationResponse,
    ImageQualityResponse,
    RegisterRequest,
    LoginRequest
)
# Database removed - crud operations no longer used
# from app.crud import create_user, get_user_by_email, create_document
from app.security import (
    create_access_token,
    decode_access_token,
    verify_password,
    hash_password,
    password_needs_rehash
)
from app.config import (
    CSV_EXPORT_DIR,
    MAX_UPLOAD_BYTES,
    JWT_SECRET
)
from api.auth import auth_scheme
from api.extraction_api import extract_text
from api.verification_api import verify_data
from fastapi.security import HTTPAuthorizationCredentials
from app.image_processing import pil_to_cv, cv_to_pil
from ocr.extraction.template_config import (
    save_templates_to_file,
    load_templates_from_file,
    add_document_type_template,
    export_template_schema
)
from ocr.extraction.field_mapper import (
    get_available_fields,
    add_custom_field_template
)

router = APIRouter()

# -------------------------
# Helper functions
# -------------------------
def get_current_user(creds: Optional[HTTPAuthorizationCredentials] = Depends(auth_scheme)):
    """Get current user (optional for web demo). Database removed - just validates token."""
    if not creds or not creds.credentials:
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

# -------------------------
# Auth routes
# -------------------------
MIN_PASSWORD_CHARS = 6
MAX_PASSWORD_CHARS = 128

@router.post("/auth/register")
def register(payload: RegisterRequest):
    """Register a new user. Database removed - returns token without storing user."""
    if not payload.password or len(payload.password) < MIN_PASSWORD_CHARS:
        raise HTTPException(
            status_code=400,
            detail=f"Password must be at least {MIN_PASSWORD_CHARS} characters"
        )
    if len(payload.password) > MAX_PASSWORD_CHARS:
        raise HTTPException(
            status_code=400,
            detail=f"Password too long. Max {MAX_PASSWORD_CHARS} characters allowed."
        )
    
    from urllib.parse import quote_plus
    avatar_url = f"https://ui-avatars.com/api/?name={quote_plus(payload.name)}&background=6d28d9&color=ffffff&bold=true"
    token = create_access_token(subject=payload.email)
    return JSONResponse({
        "user": {
            "id": 0,  # No database ID
            "name": payload.name,
            "email": payload.email,
            "avatar": avatar_url
        },
        "token": token
    })

@router.post("/auth/login")
def login(payload: LoginRequest):
    """Login and get access token. Database removed - accepts any credentials."""
    # Database removed - authentication disabled
    # In production, you should implement proper authentication
    token = create_access_token(subject=payload.email)
    return {"access_token": token, "token_type": "bearer"}

# -------------------------
# OCR endpoints
# -------------------------
@router.post("/ocr/extract")
async def ocr_extract(
    file: UploadFile = File(...),
    language: str = Form("eng"),
    run_table_ocr: Optional[bool] = Form(True),
    enable_multistage: Optional[bool] = Form(True),
    handwriting_mode: Optional[str] = Form(None),
    current_user: Optional[dict] = Depends(get_current_user)
):
    """Extract text from document using OCR."""
    return await extract_text(
        file=file,
        language=language,
        run_table_ocr=run_table_ocr,
        enable_multistage=enable_multistage,
        handwriting_mode=handwriting_mode,
        current_user=current_user
    )

@router.post("/ocr/classify")
async def ocr_classify_document(
    file: UploadFile = File(...),
    language: str = Form("eng"),
    current_user: Optional[dict] = Depends(get_current_user)
):
    """
    Classify document type and suggest appropriate field templates.
    """
    try:
        from ocr.extraction.document_classifier import classify_document, DocumentType
        from ocr.extraction.extractor import perform_extraction
        
        file_bytes = await file.read()
        if not file_bytes:
            raise HTTPException(status_code=400, detail="Empty file")
        
        # Quick OCR extraction for classification
        raw_text, fields, pages, tables = perform_extraction(
            file_bytes=file_bytes,
            filename=file.filename or "file",
            content_type=file.content_type or "",
            language=language,
            run_table_ocr=False,  # Faster without table detection
            enable_multistage=False
        )
        
        # Classify document
        doc_type, confidence = classify_document(text=raw_text)
        
        # Get recommended field templates
        from ocr.extraction.document_classifier import get_classifier
        classifier = get_classifier()
        recommended_fields = classifier.get_field_templates(doc_type)
        
        return JSONResponse(content={
            "document_type": doc_type.value,
            "confidence": confidence,
            "recommended_fields": recommended_fields,
            "extracted_fields": list(fields.keys()),
            "pages": pages
        })
    except HTTPException:
        raise
    except Exception as e:
        tb = traceback.format_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Document classification failed: {e}\\n{tb}"
        )


@router.post("/ocr/verify", response_model=VerificationResponse)
async def ocr_verify(
    file: UploadFile = File(...),
    fields_json: str = Form(...),
    language: str = Form("eng"),
    run_table_ocr: Optional[bool] = Form(True),
    handwriting_mode: Optional[str] = Form(None),
    current_user: Optional[dict] = Depends(get_current_user)
):
    """Verify submitted data against extracted OCR data."""
    return await verify_data(
        file=file,
        fields_json=fields_json,
        language=language,
        run_table_ocr=run_table_ocr,
        handwriting_mode=handwriting_mode,
        current_user=current_user
    )

# -------------------------
# Image quality endpoint
# -------------------------
@router.post("/image/quality", response_model=ImageQualityResponse)
async def image_quality(file: UploadFile = File(...)):
    """Analyze image quality metrics."""
    try:
        file_bytes = await file.read()
        if not file_bytes:
            raise HTTPException(status_code=400, detail="Empty file")
        if MAX_UPLOAD_BYTES and len(file_bytes) > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"File too large ({len(file_bytes)} bytes)"
            )
        
        img = Image.open(BytesIO(file_bytes))
        cv_img = pil_to_cv(img)
        gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
        
        # Blur score
        lap = cv2.Laplacian(gray, cv2.CV_64F)
        blur_score = float(lap.var())
        
        # Noise score
        noise_score = float(
            (gray.astype("float32") - cv2.GaussianBlur(gray, (3, 3), 0)).std()
        )
        
        # Brightness score
        brightness_score = float(gray.mean())
        
        # Table detection
        has_table_like = False
        edges = cv2.Canny(gray, 50, 150)
        lines = cv2.HoughLinesP(
            edges, 1, np.pi/180, 80, minLineLength=50, maxLineGap=5
        )
        if lines is not None and len(lines) > 10:
            has_table_like = True
        
        # Quality assessment
        if blur_score < 80 or noise_score > 30 or brightness_score < 60 or brightness_score > 230:
            quality_label = "poor"
            suggest_retake = True
        else:
            quality_label = "good"
            suggest_retake = False
        
        return ImageQualityResponse(
            blur_score=blur_score,
            brightness_score=brightness_score,
            noise_score=noise_score,
            quality_label=quality_label,
            has_table_like_structure=has_table_like,
            suggest_retake=suggest_retake
        )
    except HTTPException:
        raise
    except Exception as e:
        tb = traceback.format_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Quality check failed: {e}\n{tb}"
        )

# -------------------------
# Document endpoints (disabled - database removed)
# -------------------------
@router.get("/documents")
def list_documents(
    current_user: Optional[dict] = Depends(get_current_user)
):
    """List all documents. Database removed - returns empty list."""
    return []

@router.get("/documents/{document_id}/original")
def get_original_document(
    document_id: int,
    current_user: Optional[dict] = Depends(get_current_user)
):
    """Get original document file. Database removed - not available."""
    raise HTTPException(status_code=404, detail="Database removed - documents not stored")

@router.get("/documents/{document_id}/ocr", response_class=PlainTextResponse)
def get_ocr_text(
    document_id: int,
    current_user: Optional[dict] = Depends(get_current_user)
):
    """Get OCR text for a document. Database removed - not available."""
    raise HTTPException(status_code=404, detail="Database removed - documents not stored")

@router.get("/documents/{document_id}/tables/{page_idx}/{table_id}/csv")
def export_table_csv(
    document_id: int,
    page_idx: int,
    table_id: int,
    current_user: Optional[dict] = Depends(get_current_user)
):
    """Export table as CSV. Database removed - not available."""
    raise HTTPException(status_code=404, detail="Database removed - documents not stored")

# -------------------------
# Template Management endpoints
# -------------------------
@router.get("/templates/schema")
def get_template_schema(
    current_user: Optional[dict] = Depends(get_current_user)
):
    """Get current template schema."""
    schema = export_template_schema()
    return schema

@router.post("/templates/add")
def add_template(
    field_name: str = Form(...),
    patterns: str = Form(...),  # JSON array of patterns
    value_patterns: Optional[str] = Form(None),  # JSON array
    synonyms: Optional[str] = Form(None),  # JSON array
    current_user: Optional[dict] = Depends(get_current_user)
):
    """Add a custom field template."""
    try:
        patterns_list = json.loads(patterns)
        value_patterns_list = json.loads(value_patterns) if value_patterns else None
        synonyms_list = json.loads(synonyms) if synonyms else None
        
        add_custom_field_template(
            field_name=field_name,
            patterns=patterns_list,
            value_patterns=value_patterns_list,
            synonyms=synonyms_list
        )
        
        return {"status": "success", "message": f"Template '{field_name}' added"}
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON in patterns")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/templates/save")
def save_templates(
    file_path: Optional[str] = Form(None),
    current_user: Optional[dict] = Depends(get_current_user)
):
    """Save templates to file."""
    try:
        save_templates_to_file(file_path)
        return {"status": "success", "message": "Templates saved"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/templates/load")
def load_templates(
    file_path: Optional[str] = Form(None),
    current_user: Optional[dict] = Depends(get_current_user)
):
    """Load templates from file."""
    try:
        success = load_templates_from_file(file_path)
        if success:
            return {"status": "success", "message": "Templates loaded"}
        else:
            raise HTTPException(status_code=404, detail="Template file not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/templates/check-fields")
def check_available_fields(
    text: str = Form(...),
    current_user: Optional[dict] = Depends(get_current_user)
):
    """Check which fields are available in text."""
    try:
        available = get_available_fields(text)
        return {
            "available_fields": list(available),
            "count": len(available)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


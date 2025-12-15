# app/schemas.py
from typing import Dict, List, Optional
from pydantic import BaseModel

class ExtractResponse(BaseModel):
    document_id: int
    language: str
    pages: int
    raw_text: str
    fields: Dict[str, str]
    field_confidences: Optional[Dict[str, float]] = None  # Confidence score for each field (0-1)
    available_fields: Optional[List[str]] = None  # List of dynamically detected fields

class FieldVerificationResult(BaseModel):
    field: str
    submitted: str
    extracted: Optional[str]
    similarity: float
    status: str  # match, partial, mismatch, not_found

class VerificationResponse(BaseModel):
    document_id: int
    verification_id: int
    language: str
    pages: int
    overall_confidence: float
    field_results: List[FieldVerificationResult]
    extracted_fields: Dict[str, str]
    raw_text: str

class ImageQualityResponse(BaseModel):
    blur_score: float
    brightness_score: float
    noise_score: float
    quality_label: str
    has_table_like_structure: bool
    suggest_retake: bool

class TableCell(BaseModel):
    x: int
    y: int
    w: int
    h: int
    text: Optional[str] = None

class TableDetected(BaseModel):
    table_id: int
    bbox: Dict[str,int]
    cells: List[TableCell]

class AuthUser(BaseModel):
    id: int
    name: str
    email: str
    avatar: Optional[str] = None

class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str

class LoginRequest(BaseModel):
    email: str
    password: str

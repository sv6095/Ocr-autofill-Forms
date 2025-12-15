"""
Document type parser and classification.
"""
from enum import Enum
from typing import Optional, Dict
import re


class DocumentType(Enum):
    """Document type enumeration."""
    ID_CARD = "id_card"
    PASSPORT = "passport"
    DRIVER_LICENSE = "driver_license"
    CERTIFICATE = "certificate"
    FORM = "form"
    INVOICE = "invoice"
    RECEIPT = "receipt"
    UNKNOWN = "unknown"


def detect_document_type(text: str, filename: Optional[str] = None) -> DocumentType:
    """
    Detect document type from text and filename.
    
    Args:
        text: Extracted OCR text
        filename: Original filename (optional)
    
    Returns:
        DocumentType enum
    """
    text_lower = text.lower()
    filename_lower = (filename or "").lower()
    
    # Check for ID card patterns
    id_patterns = [
        r"aadhaar",
        r"pan\s+card",
        r"voter\s+id",
        r"driving\s+licen[cs]e",
        r"drl\s+no",
    ]
    for pattern in id_patterns:
        if re.search(pattern, text_lower):
            if "aadhaar" in text_lower or "aadhar" in text_lower:
                return DocumentType.ID_CARD
            if "driving" in text_lower or "drl" in text_lower:
                return DocumentType.DRIVER_LICENSE
            return DocumentType.ID_CARD
    
    # Check for passport
    if re.search(r"passport|passport\s+no", text_lower):
        return DocumentType.PASSPORT
    
    # Check for certificate
    cert_patterns = [
        r"certificate",
        r"this\s+is\s+to\s+certify",
        r"degree",
        r"diploma",
    ]
    for pattern in cert_patterns:
        if re.search(pattern, text_lower):
            return DocumentType.CERTIFICATE
    
    # Check for form
    form_patterns = [
        r"application\s+form",
        r"registration\s+form",
        r"form\s+no",
    ]
    for pattern in form_patterns:
        if re.search(pattern, text_lower):
            return DocumentType.FORM
    
    # Check for invoice/receipt
    if re.search(r"invoice|bill\s+no", text_lower):
        return DocumentType.INVOICE
    if re.search(r"receipt|payment", text_lower):
        return DocumentType.RECEIPT
    
    # Check filename
    if filename:
        if "passport" in filename_lower:
            return DocumentType.PASSPORT
        if "certificate" in filename_lower or "cert" in filename_lower:
            return DocumentType.CERTIFICATE
        if "form" in filename_lower:
            return DocumentType.FORM
    
    return DocumentType.UNKNOWN


def parse_document_metadata(text: str, doc_type: DocumentType) -> Dict[str, str]:
    """
    Parse document-specific metadata based on type.
    
    Args:
        text: Extracted OCR text
        doc_type: Detected document type
    
    Returns:
        Dictionary of metadata fields
    """
    metadata = {}
    
    if doc_type == DocumentType.ID_CARD:
        # Extract Aadhaar number
        aadhaar_match = re.search(r"(\d{4}\s?\d{4}\s?\d{4})", text)
        if aadhaar_match:
            metadata["aadhaar_number"] = aadhaar_match.group(1).replace(" ", "")
        
        # Extract PAN
        pan_match = re.search(r"([A-Z]{5}\d{4}[A-Z])", text)
        if pan_match:
            metadata["pan_number"] = pan_match.group(1)
    
    elif doc_type == DocumentType.PASSPORT:
        # Extract passport number
        passport_match = re.search(r"passport\s+no[.:]?\s*([A-Z0-9]+)", text, re.IGNORECASE)
        if passport_match:
            metadata["passport_number"] = passport_match.group(1)
    
    elif doc_type == DocumentType.DRIVER_LICENSE:
        # Extract license number
        license_match = re.search(r"(?:licen[cs]e|dl)\s+no[.:]?\s*([A-Z0-9]+)", text, re.IGNORECASE)
        if license_match:
            metadata["license_number"] = license_match.group(1)
    
    return metadata


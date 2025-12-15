"""
Document type classification for OCR processing.
Identifies common document types to optimize OCR and field extraction.
"""
from typing import Dict, Optional, Tuple, List
from enum import Enum
import re
from PIL import Image
import numpy as np


class DocumentType(Enum):
    """Document type enumeration."""
    AADHAAR_CARD = "aadhaar_card"
    PAN_CARD = "pan_card"
    PASSPORT = "passport"
    DRIVERS_LICENSE = "drivers_license"
    VOTER_ID = "voter_id"
    BIRTH_CERTIFICATE = "birth_certificate"
    MARKSHEET = "marksheet"
    APPLICATION_FORM = "application_form"
    INVOICE = "invoice"
    RECEIPT = "receipt"
    BANK_STATEMENT = "bank_statement"
    HANDWRITTEN_NOTE = "handwritten_note"
    GENERIC = "generic"


class DocumentClassifier:
    """Classify document types based on content and structure."""
    
    def __init__(self):
        """Initialize document classifier with pattern templates."""
        self.patterns = {
            DocumentType.AADHAAR_CARD: {
                "keywords": [
                    r"aadhaar",
                    r"aadhar",
                    r"uid",
                    r"unique\s+identification",
                    r"government\s+of\s+india",
                    r"\d{4}\s+\d{4}\s+\d{4}",  # Aadhaar number pattern
                ],
                "size_ratio": (1.6, 1.7),  # Width/height ratio for ID card
                "confidence_threshold": 0.4
            },
            DocumentType.PAN_CARD: {
                "keywords": [
                    r"income\s+tax\s+department",
                    r"permanent\s+account\s+number",
                    r"[A-Z]{5}\d{4}[A-Z]",  # PAN pattern
                    r"father'?s?\s+name",
                ],
                "size_ratio": (1.5, 1.7),
                "confidence_threshold": 0.4
            },
            DocumentType.PASSPORT: {
                "keywords": [
                    r"passport",
                    r"republic\s+of\s+india",
                    r"nationality",
                    r"surname",
                    r"given\s+name",
                    r"date\s+of\s+birth",
                    r"place\s+of\s+birth",
                    r"date\s+of\s+issue",
                    r"date\s+of\s+expiry",
                ],
                "size_ratio": (0.65, 0.75),  # Passport booklet page ratio
                "confidence_threshold": 0.5
            },
            DocumentType.DRIVERS_LICENSE: {
                "keywords": [
                    r"driving\s+licen[cs]e",
                    r"transport\s+authority",
                    r"vehicle\s+class",
                    r"valid\s+till",
                    r"dl\s+no",
                ],
                "size_ratio": (1.5, 1.7),
                "confidence_threshold": 0.4
            },
            DocumentType.VOTER_ID: {
                "keywords": [
                    r"election\s+commission",
                    r"voter\s+id",
                    r"elector'?s?\s+photo\s+identity\s+card",
                    r"epic",
                ],
                "size_ratio": (1.5, 1.7),
                "confidence_threshold": 0.4
            },
            DocumentType.BIRTH_CERTIFICATE: {
                "keywords": [
                    r"birth\s+certificate",
                    r"date\s+of\s+birth",
                    r"place\s+of\s+birth",
                    r"father'?s?\s+name",
                    r"mother'?s?\s+name",
                    r"municipal\s+corporation",
                    r"registrar",
                ],
                "size_ratio": None,  # Variable
                "confidence_threshold": 0.5
            },
            DocumentType.MARKSHEET: {
                "keywords": [
                    r"marksheet",
                    r"mark\s+sheet",
                    r"grade\s+card",
                    r"examination",
                    r"university",
                    r"subject",
                    r"marks\s+obtained",
                    r"total\s+marks",
                    r"cgpa",
                    r"percentage",
                ],
                "size_ratio": None,
                "confidence_threshold": 0.4
            },
            DocumentType.APPLICATION_FORM: {
                "keywords": [
                    r"application\s+form",
                    r"applicant'?s?\s+name",
                    r"date\s+of\s+birth",
                    r"address",
                    r"contact\s+number",
                    r"email",
                    r"signature",
                    r"declaration",
                ],
                "size_ratio": None,
                "confidence_threshold": 0.3
            },
            DocumentType.INVOICE: {
                "keywords": [
                    r"invoice",
                    r"bill\s+to",
                    r"ship\s+to",
                    r"invoice\s+no",
                    r"invoice\s+date",
                    r"subtotal",
                    r"tax",
                    r"total\s+amount",
                    r"gstin",
                ],
                "size_ratio": None,
                "confidence_threshold": 0.4
            },
            DocumentType.HANDWRITTEN_NOTE: {
                "keywords": [],  # Detected by image analysis
                "size_ratio": None,
                "confidence_threshold": 0.6
            }
        }
    
    def classify_from_text(self, text: str) -> Tuple[DocumentType, float]:
        """
        Classify document type from extracted text.
        
        Args:
            text: OCR extracted text
            
        Returns:
            Tuple of (DocumentType, confidence_score)
        """
        if not text or not text.strip():
            return DocumentType.GENERIC, 0.0
        
        text_lower = text.lower()
        scores = {}
        
        for doc_type, config in self.patterns.items():
            if doc_type == DocumentType.HANDWRITTEN_NOTE:
                continue  # Handled by image analysis
            
            keywords = config["keywords"]
            matches = 0
            for pattern in keywords:
                if re.search(pattern, text_lower):
                    matches += 1
            
            if keywords:
                confidence = matches / len(keywords)
                scores[doc_type] = confidence
        
        if not scores:
            return DocumentType.GENERIC, 0.0
        
        best_type = max(scores, key=scores.get)
        best_confidence = scores[best_type]
        
        threshold = self.patterns[best_type]["confidence_threshold"]
        if best_confidence >= threshold:
            return best_type, best_confidence
        
        return DocumentType.GENERIC, best_confidence
    
    def classify_from_image(self, image: Image.Image, text: Optional[str] = None) -> Tuple[DocumentType, float]:
        """
        Classify document type from image and optional text.
        
        Args:
            image: PIL Image
            text: Optional OCR text (if already extracted)
            
        Returns:
            Tuple of (DocumentType, confidence_score)
        """
        # Get aspect ratio
        width, height = image.size
        aspect_ratio = width / height if height > 0 else 1.0
        
        # First classify from text if available
        if text:
            doc_type, text_confidence = self.classify_from_text(text)
            
            # Verify aspect ratio if we have a specific match
            if doc_type != DocumentType.GENERIC:
                expected_ratio = self.patterns[doc_type]["size_ratio"]
                if expected_ratio:
                    min_ratio, max_ratio = expected_ratio
                    if min_ratio <= aspect_ratio <= max_ratio:
                        # Boost confidence if aspect ratio matches
                        return doc_type, min(1.0, text_confidence * 1.2)
                    else:
                        # Reduce confidence if aspect ratio doesn't match
                        return doc_type, text_confidence * 0.8
                
                return doc_type, text_confidence
        
        # Check if image matches ID card dimensions
        if 1.5 <= aspect_ratio <= 1.7:
            return DocumentType.GENERIC, 0.3  # Could be any ID card
        
        return DocumentType.GENERIC, 0.0
    
    def get_field_templates(self, doc_type: DocumentType) -> List[str]:
        """
        Get recommended field templates for a document type.
        
        Args:
            doc_type: Document type
            
        Returns:
            List of recommended field names
        """
        templates = {
            DocumentType.AADHAAR_CARD: [
                "name", "aadhaar_number", "date_of_birth", "gender", 
                "address", "father_name"
            ],
            DocumentType.PAN_CARD: [
                "name", "pan_number", "father_name", "date_of_birth"
            ],
            DocumentType.PASSPORT: [
                "surname", "given_name", "passport_number", "nationality",
                "date_of_birth", "place_of_birth", "date_of_issue", 
                "date_of_expiry", "place_of_issue"
            ],
            DocumentType.DRIVERS_LICENSE: [
                "name", "license_number", "date_of_birth", "address",
                "date_of_issue", "valid_till", "vehicle_class"
            ],
            DocumentType.VOTER_ID: [
                "name", "voter_id", "father_name", "address", "date_of_birth"
            ],
            DocumentType.BIRTH_CERTIFICATE: [
                "name", "date_of_birth", "place_of_birth", "father_name",
                "mother_name", "registration_number"
            ],
            DocumentType.MARKSHEET: [
                "name", "roll_number", "exam_name", "university", "year",
                "subjects", "marks_obtained", "total_marks", "percentage", "grade"
            ],
            DocumentType.APPLICATION_FORM: [
                "name", "date_of_birth", "address", "phone", "email",
                "father_name", "occupation", "city", "state", "zip_code"
            ],
            DocumentType.INVOICE: [
                "invoice_number", "invoice_date", "company_name", "gstin",
                "bill_to", "subtotal", "tax", "total_amount"
            ],
        }
        
        return templates.get(doc_type, [])


# Global classifier instance
_classifier = None


def get_classifier() -> DocumentClassifier:
    """Get global document classifier instance."""
    global _classifier
    if _classifier is None:
        _classifier = DocumentClassifier()
    return _classifier


def classify_document(text: str = None, image: Image.Image = None) -> Tuple[DocumentType, float]:
    """
    Classify document type from text and/or image.
    
    Args:
        text: OCR extracted text
        image: PIL Image
        
    Returns:
        Tuple of (DocumentType, confidence_score)
    """
    classifier = get_classifier()
    
    if image and text:
        return classifier.classify_from_image(image, text)
    elif text:
        return classifier.classify_from_text(text)
    elif image:
        return classifier.classify_from_image(image)
    
    return DocumentType.GENERIC, 0.0

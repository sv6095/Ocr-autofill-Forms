"""
Enhanced field mapping from OCR text with improved patterns and templates.
"""
import re
import logging
from typing import Dict, List, Optional, Set, Tuple
from ocr.extraction.template_matcher import match_key_value_pairs

logger = logging.getLogger(__name__)


# Enhanced field templates with multiple patterns
FIELD_TEMPLATES = {
    # Personal Information
    "name": {
        "patterns": [
            r"(?:full\s+)?name\s*:?\s*([^\n]+)",
            r"applicant'?s?\s+name\s*:?\s*([^\n]+)",
            r"person\s+name\s*:?\s*([^\n]+)",
            r"^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\s*$",  # Capitalized name pattern
        ],
        "synonyms": ["full_name", "applicant_name", "person_name", "student_name"]
    },
    "father_name": {
        "patterns": [
            r"father'?s?\s+name\s*:?\s*([^\n]+)",
            r"father\s*:?\s*([^\n]+)",
        ],
        "synonyms": ["father", "fathers_name"]
    },
    "mother_name": {
        "patterns": [
            r"mother'?s?\s+name\s*:?\s*([^\n]+)",
            r"mother\s*:?\s*([^\n]+)",
        ],
        "synonyms": ["mother", "mothers_name"]
    },
    "date_of_birth": {
        "patterns": [
            r"(?:date\s+of\s+)?birth\s*:?\s*(\d{1,2}[\-/\.]\d{1,2}[\-/\.]\d{2,4})",
            r"dob\s*:?\s*(\d{1,2}[\-/\.]\d{1,2}[\-/\.]\d{2,4})",
            r"born\s+on\s*:?\s*(\d{1,2}[\-/\.]\d{1,2}[\-/\.]\d{2,4})",
        ],
        "synonyms": ["dob", "birth_date", "date_birth"]
    },
    "gender": {
        "patterns": [
            r"(?:sex|gender)\s*:?\s*(male|female|m|f|other)",
        ],
        "synonyms": ["sex"]
    },
    
    # Contact Information
    "address": {
        "patterns": [
            # Stricter address pattern - stops at phone numbers or email
            r"address\s*:?\s*((?:[^\n]+(?:\n[^\n:]+)*?)(?=\s*(?:phone|mobile|contact|tel|email|e-mail|@|\d{10,})|$))",
            r"residential\s+address\s*:?\s*((?:[^\n]+(?:\n[^\n:]+)*?)(?=\s*(?:phone|mobile|contact|tel|email|e-mail|@|\d{10,})|$))",
            r"permanent\s+address\s*:?\s*((?:[^\n]+(?:\n[^\n:]+)*?)(?=\s*(?:phone|mobile|contact|tel|email|e-mail|@|\d{10,})|$))",
            r"home\s+address\s*:?\s*((?:[^\n]+(?:\n[^\n:]+)*?)(?=\s*(?:phone|mobile|contact|tel|email|e-mail|@|\d{10,})|$))",
        ],
        "synonyms": ["addr", "residential_address", "home_address", "permanent_address"]
    },
    "phone": {
        "patterns": [
            # Stricter phone pattern - must be clearly phone-related
            r"(?:phone|mobile|contact)\s*(?:no\.?|number)?\s*:?\s*([+\d\s\-\(\)]{10,15})(?!\s*[a-zA-Z])",
            r"(?:tel|telephone)\s*:?\s*([+\d\s\-\(\)]{10,15})(?!\s*[a-zA-Z])",
            # Standalone phone number pattern (10+ digits)
            r"(?<![\d])([+\d\s\-\(\)]{10,15})(?!\s*(?:address|email|@|[a-zA-Z]{3,}))",
        ],
        "synonyms": ["mobile", "contact_number", "phone_number", "telephone"]
    },
    "email": {
        "patterns": [
            r"e?-?mail\s*:?\s*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})",
        ],
        "synonyms": ["e_mail", "email_address"]
    },
    "city": {
        "patterns": [
            r"city\s*:?\s*([^\n,]+)",
            r"town\s*:?\s*([^\n,]+)",
        ],
        "synonyms": ["town"]
    },
    "state": {
        "patterns": [
            r"state\s*:?\s*([^\n,]+)",
            r"province\s*:?\s*([^\n,]+)",
        ],
        "synonyms": ["province"]
    },
    "zip_code": {
        "patterns": [
            r"(?:zip|postal|pin)\s*(?:code)?\s*:?\s*(\d{6})",
        ],
        "synonyms": ["postal_code", "pin_code", "pincode"]
    },
    
    # Indian ID Numbers
    "aadhaar_number": {
        "patterns": [
            r"(?:aadhaar|aadhar|uid)\s*(?:no\.?|number)?\s*:?\s*(\d{4}\s*\d{4}\s*\d{4})",
            r"(\d{4}\s*\d{4}\s*\d{4})",  # 12-digit pattern
        ],
        "synonyms": ["aadhaar", "aadhar_number", "uid"]
    },
    "pan_number": {
        "patterns": [
            r"pan\s*(?:no\.?|number)?\s*:?\s*([A-Z]{5}\d{4}[A-Z])",
        ],
        "synonyms": ["pan"]
    },
    "passport_number": {
        "patterns": [
            r"passport\s*(?:no\.?|number)?\s*:?\s*([A-Z]\d{7})",
        ],
        "synonyms": ["passport"]
    },
    "license_number": {
        "patterns": [
            r"(?:license|licence|dl)\s*(?:no\.?|number)?\s*:?\s*([A-Z0-9\-\/]+)",
        ],
        "synonyms": ["dl_number", "driving_license", "licence_number"]
    },
    "voter_id": {
        "patterns": [
            r"(?:voter|epic)\s*(?:id|no\.?|number)?\s*:?\s*([A-Z]{3}\d{7})",
        ],
        "synonyms": ["epic_number", "voter_id_number"]
    },
    
    # Other  Fields
    "occupation": {
        "patterns": [
            r"occupation\s*:?\s*([^\n]+)",
            r"profession\s*:?\s*([^\n]+)",
        ],
        "synonyms": ["profession", "job"]
    },
    "blood_group": {
        "patterns": [
            r"blood\s+group\s*:?\s*([ABO][+-]?)",
            r"blood\s+type\s*:?\s*([ABO][+-]?)",
        ],
        "synonyms": ["blood_type"]
    },
    "marital_status": {
        "patterns": [
            r"marital\s+status\s*:?\s*(married|single|widowed|divorced)",
        ],
        "synonyms": ["martial_status"]  # Common typo
    },
    "nationality": {
        "patterns": [
            r"nationality\s*:?\s*([^\n]+)",
        ],
        "synonyms": ["country"]
    },
    "emergency_contact": {
        "patterns": [
            r"emergency\s+contact\s*:?\s*([^\n]+)",
        ],
        "synonyms": ["emergency_number"]
    },
}


def get_available_fields(text: str) -> Set[str]:
    """
    Scan text for available fields based on templates.
    
    Args:
        text: OCR extracted text
        
    Returns:
        Set of field names found in the text
    """
    if not text:
        return set()
    
    available = set()
    text_lower = text.lower()
    
    for field_name, config in FIELD_TEMPLATES.items():
        # Check patterns
        for pattern in config["patterns"]:
            if re.search(pattern, text_lower, re.IGNORECASE | re.MULTILINE):
                available.add(field_name)
                break
        
        # Check synonyms
        if field_name not in available:
            for synonym in config.get("synonyms", []):
                if synonym.lower() in text_lower:
                    available.add(field_name)
                    break
    
    return available


def extract_field_value(text: str, field_name: str, patterns: List[str]) -> Tuple[Optional[str], float]:
    """
    Extract field value from text using provided patterns with confidence scoring.
    
    Args:
        text: OCR text
        field_name: Name of the field
        patterns: List of regex patterns to try
        
    Returns:
        Tuple of (extracted value or None, confidence score 0-1)
    """
    best_value = None
    best_confidence = 0.0
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match:
            value = match.group(1).strip()
            # Clean up the value
            value = re.sub(r'\s+', ' ', value)  # Normalize whitespace
            value = value.strip(':').strip()
            
            if value:
                # Calculate confidence based on pattern match quality
                confidence = 0.7  # Base confidence for pattern match
                
                # Boost confidence if value looks valid
                if len(value) > 2:
                    confidence += 0.1
                if len(value) > 5:
                    confidence += 0.1
                
                # Boost if value doesn't contain common OCR errors
                if not re.search(r'[^\w\s@.\-+()]', value):
                    confidence += 0.1
                
                # Penalize if value looks like it contains other field types
                # Stricter matching - avoid cross-contamination
                if field_name == "address":
                    # Address should not contain phone patterns
                    if re.search(r'\d{10,}', value):
                        confidence -= 0.3
                    # Address should not contain email
                    if '@' in value:
                        confidence -= 0.2
                elif field_name == "phone":
                    # Phone should be mostly digits
                    digit_ratio = len(re.findall(r'\d', value)) / max(len(value), 1)
                    if digit_ratio < 0.6:
                        confidence -= 0.3
                elif field_name == "email":
                    # Email must contain @
                    if '@' not in value:
                        confidence = 0.0
                    else:
                        confidence += 0.1
                
                confidence = min(1.0, max(0.0, confidence))
                
                if confidence > best_confidence:
                    best_value = value
                    best_confidence = confidence
    
    return best_value, best_confidence


def map_fields_from_text(
    text: str,
    use_template_matching: bool = True,
    partial: bool = True,
    field_names: Optional[List[str]] = None
) -> Tuple[Dict[str, str], Dict[str, float]]:
    """
    Map fields from OCR text using enhanced templates with confidence scoring.
    
    Args:
        text: OCR extracted text
        use_template_matching: Use template matcher from template_matcher module
        partial: Only extract fields that are present in the text (dynamic extraction)
        field_names: Specific field names to extract (None = all, enables dynamic extraction)
        
    Returns:
        Tuple of (fields dictionary, confidence scores dictionary)
        Both dictionaries have field_name as key
    """
    logger.debug(f"map_fields_from_text called with text length: {len(text) if text else 0}")
    
    if not text or not text.strip():
        logger.debug("map_fields_from_text: Empty text, returning empty dict")
        return {}, {}
    
    logger.debug(f"map_fields_from_text: Text preview (first 200 chars): {text[:200]}")
    
    fields = {}
    confidences = {}
    template_fields_count = 0
    
    # First, try template matching for key-value pairs (more lenient)
    if use_template_matching:
        try:
            template_fields = match_key_value_pairs(text)
            template_fields_count = len(template_fields)
            logger.debug(f"Template matching found {template_fields_count} fields: {list(template_fields.keys())}")
            # Add template matched fields with default confidence
            for key, value in template_fields.items():
                if value and value.strip():
                    fields[key] = value.strip()
                    confidences[key] = 0.6  # Default confidence for template matches
        except Exception as e:
            # Template matching failed, continue with pattern matching
            logger.debug(f"Template matching failed: {e}")
            pass
    
    # Dynamic field extraction - get all available fields (no restrictions)
    if partial:
        available_fields = get_available_fields(text)
        logger.debug(f"get_available_fields found {len(available_fields)} fields: {list(available_fields)}")
    else:
        # If not partial, try all known fields
        available_fields = set(FIELD_TEMPLATES.keys())
    
    # Only filter by requested field names if explicitly provided
    # Otherwise, extract all available fields dynamically
    if field_names:
        available_fields = available_fields.intersection(set(field_names))
    
    # Extract each available field using pattern matching with confidence
    for field_name in available_fields:
        if field_name not in FIELD_TEMPLATES:
            continue
        
        config = FIELD_TEMPLATES[field_name]
        patterns = config["patterns"]
        
        value, confidence = extract_field_value(text, field_name, patterns)
        if value and value.strip():
            # Prefer pattern-matched values over template-matched (more accurate)
            # Only update if confidence is higher or field doesn't exist
            if field_name not in fields or confidence > confidences.get(field_name, 0.0):
                fields[field_name] = value.strip()
                confidences[field_name] = confidence
                logger.debug(f"Extracted field '{field_name}': '{value.strip()}' (confidence: {confidence:.2f})")
    
    # Also extract generic key-value pairs (e.g., "Name: John Doe")
    generic_count = 0
    for line in text.split('\n'):
        line = line.strip()
        if ':' in line:
            parts = line.split(':', 1)
            if len(parts) == 2:
                key = parts[0].strip().lower()
                value = parts[1].strip()
                if value and key and key not in fields:
                    # Normalize key
                    key_normalized = re.sub(r'[^\w\s]', '', key)
                    key_normalized = re.sub(r'\s+', '_', key_normalized)
                    if key_normalized and len(key_normalized) > 1:
                        fields[key_normalized] = value
                        confidences[key_normalized] = 0.5  # Lower confidence for generic matches
                        generic_count += 1
                        logger.debug(f"Extracted generic field '{key_normalized}': '{value}'")
    
    pattern_matched_count = len([f for f in fields if f in available_fields])
    logger.debug(f"Total fields extracted: {len(fields)} (template: {template_fields_count}, pattern: {pattern_matched_count}, generic: {generic_count})")
    logger.debug(f"Final fields: {list(fields.keys())}")
    logger.debug(f"Field confidences: {confidences}")
    
    return fields, confidences


def add_custom_field_template(
    field_name: str,
    patterns: List[str],
    value_patterns: Optional[List[str]] = None,
    synonyms: Optional[List[str]] = None
):
    """
    Add a custom field template for extraction.
    
    Args:
        field_name: Name of the field
        patterns: List of regex patterns to match the field
        value_patterns: Optional list of patterns to extract the value
        synonyms: Optional list of synonym field names
    """
    FIELD_TEMPLATES[field_name] = {
        "patterns": patterns,
        "value_patterns": value_patterns or [],
        "synonyms": synonyms or []
    }


def get_field_template(field_name: str) -> Optional[Dict]:
    """Get template configuration for a field."""
    return FIELD_TEMPLATES.get(field_name)


def list_all_field_names() -> List[str]:
    """Get list of all supported field names."""
    return list(FIELD_TEMPLATES.keys())

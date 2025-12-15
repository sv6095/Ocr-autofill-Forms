"""
Data validation for extracted fields.
"""
import re
from typing import Dict, Optional, Tuple
from datetime import datetime


def validate_date(date_str: str) -> Tuple[bool, Optional[str]]:
    """
    Validate date string format.
    
    Returns:
        Tuple of (is_valid, normalized_date)
    """
    if not date_str:
        return False, None
    
    # Try common date formats
    formats = [
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%Y-%m-%d",
        "%d/%m/%y",
        "%d-%m-%y",
    ]
    
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str.strip(), fmt)
            return True, dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    
    return False, None


def validate_email(email: str) -> bool:
    """Validate email format."""
    if not email:
        return False
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email.strip()))


def validate_phone(phone: str) -> bool:
    """Validate phone number format."""
    if not phone:
        return False
    # Remove spaces, dashes, parentheses
    cleaned = re.sub(r"[\s\-\(\)]", "", phone)
    # Check if it's all digits and reasonable length
    return cleaned.isdigit() and 10 <= len(cleaned) <= 15


def validate_aadhaar(aadhaar: str) -> bool:
    """Validate Aadhaar number format."""
    if not aadhaar:
        return False
    # Remove spaces
    cleaned = re.sub(r"\s", "", aadhaar)
    # Should be 12 digits
    return cleaned.isdigit() and len(cleaned) == 12


def validate_pan(pan: str) -> bool:
    """Validate PAN number format."""
    if not pan:
        return False
    # Remove spaces
    cleaned = re.sub(r"\s", "", pan.upper())
    # Format: ABCDE1234F (5 letters, 4 digits, 1 letter)
    pattern = r"^[A-Z]{5}\d{4}[A-Z]$"
    return bool(re.match(pattern, cleaned))


def validate_field(field_name: str, field_value: str) -> Tuple[bool, Optional[str]]:
    """
    Validate a field based on its name and value.
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not field_value or not field_value.strip():
        return False, "Field is empty"
    
    field_lower = field_name.lower()
    
    if "date" in field_lower or "dob" in field_lower:
        is_valid, normalized = validate_date(field_value)
        if not is_valid:
            return False, "Invalid date format"
        return True, None
    
    if "email" in field_lower:
        if not validate_email(field_value):
            return False, "Invalid email format"
        return True, None
    
    if "phone" in field_lower or "mobile" in field_lower:
        if not validate_phone(field_value):
            return False, "Invalid phone number format"
        return True, None
    
    if "aadhaar" in field_lower or "aadhar" in field_lower:
        if not validate_aadhaar(field_value):
            return False, "Invalid Aadhaar number format"
        return True, None
    
    if "pan" in field_lower:
        if not validate_pan(field_value):
            return False, "Invalid PAN format"
        return True, None
    
    # Default: non-empty is valid
    return True, None


def validate_extracted_fields(fields: Dict[str, str]) -> Dict[str, Tuple[bool, Optional[str]]]:
    """
    Validate all extracted fields.
    
    Returns:
        Dictionary mapping field_name -> (is_valid, error_message)
    """
    results = {}
    for field_name, field_value in fields.items():
        is_valid, error = validate_field(field_name, field_value)
        results[field_name] = (is_valid, error)
    return results


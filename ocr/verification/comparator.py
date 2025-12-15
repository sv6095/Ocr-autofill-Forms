"""
Compare extracted OCR data with submitted user data.
Enhanced with fuzzy matching and field-specific comparison strategies.
"""
from typing import Dict, List, Tuple
from difflib import SequenceMatcher
try:
    from rapidfuzz import fuzz, process
    RAPIDFUZZ_AVAILABLE = True
except ImportError:
    RAPIDFUZZ_AVAILABLE = False

from app.schemas import FieldVerificationResult


def _similarity(a: str, b: str) -> float:
    """Calculate similarity ratio between two strings."""
    return SequenceMatcher(None, a.strip().lower(), b.strip().lower()).ratio()


def _fuzzy_similarity(a: str, b: str) -> float:
    """
    Calculate fuzzy similarity using rapidfuzz if available.
    Falls back to SequenceMatcher if not available.
    """
    if not RAPIDFUZZ_AVAILABLE:
        return _similarity(a, b)
    
    # Use token_sort_ratio for better handling of word order differences
    return fuzz.token_sort_ratio(a.strip(), b.strip()) / 100.0


def _name_similarity(a: str, b: str) -> float:
    """
    Calculate similarity for name fields with special handling.
    Handles initials, middle name variations, and common name patterns.
    """
    if not a or not b:
        return 0.0
    
    a_clean = a.strip().lower()
    b_clean = b.strip().lower()
    
    # Exact match
    if  a_clean == b_clean:
        return 1.0
    
    # Check fuzzy match
    if RAPIDFUZZ_AVAILABLE:
        # Partial ratio helps with initials and middle name differences
        partial = fuzz.partial_ratio(a_clean, b_clean) / 100.0
        token_sort = fuzz.token_sort_ratio(a_clean, b_clean) / 100.0
        # Use the better of the two scores
        return max(partial, token_sort)
    
    return _similarity(a, b)


def _address_similarity(a: str, b: str) -> float:
    """
    Calculate similarity for address fields.
    More tolerant of word order and abbreviations.
    """
    if not a or not b:
        return 0.0
    
    if RAPIDFUZZ_AVAILABLE:
        # Token set ratio ignores duplicate words and word order
        return fuzz.token_set_ratio(a.strip(), b.strip()) / 100.0
    
    return _similarity(a, b)


def _number_similarity(a: str, b: str) -> float:
    """
    Calculate similarity for number fields (phone, ID numbers, etc.).
    Requires higher precision, removes spaces and dashes.
    """
    if not a or not b:
        return 0.0
    
    # Remove common separators
    import re
    a_digits = re.sub(r'[\s\-\(\)]', '', a.strip())
    b_digits = re.sub(r'[\s\-\(\)]', '', b.strip())
    
    # Exact match required for numbers
    if a_digits == b_digits:
        return 1.0
    
    # Partial match for partial numbers (e.g., last 4 digits of phone)
    if RAPIDFUZZ_AVAILABLE:
        return fuzz.ratio(a_digits, b_digits) / 100.0
    
    return _similarity(a_digits, b_digits)


def _get_field_similarity_function(field_name: str):
    """
    Get the appropriate similarity function for a field type.
    """
    field_lower = field_name.lower()
    
    # Name fields
    if any(x in field_lower for x in ['name', 'father', 'mother', 'guardian', 'spouse']):
        return _name_similarity
    
    # Address fields
    if any(x in field_lower for x in ['address', 'addr', 'location', 'city', 'state']):
        return _address_similarity
    
    # Number fields
    if any(x in field_lower for x in [
        'phone', 'mobile', 'contact', 'number', 'aadhaar', 'aadhar',
        'pan', 'passport', 'license', 'id', 'zip', 'pin', 'code'
    ]):
        return _number_similarity
    
    # Default to fuzzy similarity
    return _fuzzy_similarity


def verify_submitted_data(
    submitted_data: Dict[str, str],
    extracted_fields: Dict[str, str]
) -> Tuple[List[FieldVerificationResult], float]:
    """
    Verify submitted data against extracted OCR fields.
    Uses field-specific comparison strategies for better accuracy.
    
    Args:
        submitted_data: User-submitted field values
        extracted_fields: Fields extracted from OCR
    
    Returns:
        Tuple of (field_results_list, overall_confidence)
    """
    lower_key_map = {k.lower(): k for k in extracted_fields.keys()}
    results = []
    scores = []
    
    for field, submitted_value in submitted_data.items():
        field_lower = field.lower()
        extracted_value = None
        
        # Try to find matching field in extracted data
        if field in extracted_fields:
            extracted_value = extracted_fields[field]
        elif field_lower in lower_key_map:
            extracted_value = extracted_fields[lower_key_map[field_lower]]
        else:
            # Try fuzzy field name matching if available
            if RAPIDFUZZ_AVAILABLE and extracted_fields:
                match = process.extractOne(
                    field,
                    extracted_fields.keys(),
                    scorer=fuzz.ratio,
                    score_cutoff=70
                )
                if match:
                    extracted_value = extracted_fields[match[0]]
        
        if extracted_value is None:
            fr = FieldVerificationResult(
                field=field,
                submitted=str(submitted_value),
                extracted=None,
                similarity=0.0,
                status="not_found"
            )
            results.append(fr)
            scores.append(0.0)
            continue
        
        # Get field-specific similarity function
        similarity_fn = _get_field_similarity_function(field)
        sim = similarity_fn(str(submitted_value), str(extracted_value))
        
        # Determine status based on similarity
        if sim >= 0.9:
            status = "match"
        elif sim >= 0.6:
            status = "partial"
        else:
            status = "mismatch"
        
        fr = FieldVerificationResult(
            field=field,
            submitted=str(submitted_value),
            extracted=str(extracted_value),
            similarity=sim,
            status=status
        )
        results.append(fr)
        scores.append(sim)
    
    overall_confidence = sum(scores) / len(scores) if scores else 0.0
    return results, overall_confidence

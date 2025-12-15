"""
Confidence scoring for OCR results.
"""
from typing import Dict, List, Optional
import statistics


def calculate_field_confidence(
    extracted_value: str,
    ocr_confidence: float = 0.0,
    text_length: int = 0
) -> float:
    """
    Calculate confidence score for a single field.
    
    Args:
        extracted_value: Extracted field value
        ocr_confidence: Base OCR confidence (0-1)
        text_length: Length of extracted text
    
    Returns:
        Confidence score (0-1)
    """
    if not extracted_value or not extracted_value.strip():
        return 0.0
    
    # Base confidence from OCR engine
    base_conf = ocr_confidence
    
    # Length factor (longer text is more reliable)
    length_factor = min(1.0, text_length / 20.0)
    
    # Combine factors
    confidence = base_conf * 0.7 + length_factor * 0.3
    
    return min(1.0, max(0.0, confidence))


def calculate_overall_confidence(
    field_confidences: List[float],
    weights: Optional[Dict[str, float]] = None
) -> float:
    """
    Calculate overall confidence from field confidences.
    
    Args:
        field_confidences: List of confidence scores
        weights: Optional weights for each field
    
    Returns:
        Overall confidence score (0-1)
    """
    if not field_confidences:
        return 0.0
    
    if weights:
        # Weighted average
        weighted_sum = sum(
            conf * weights.get(f"field_{i}", 1.0)
            for i, conf in enumerate(field_confidences)
        )
        total_weight = sum(weights.values())
        return weighted_sum / total_weight if total_weight > 0 else 0.0
    else:
        # Simple average
        return statistics.mean(field_confidences)


def assess_verification_confidence(
    similarity_scores: List[float],
    match_threshold: float = 0.9,
    partial_threshold: float = 0.6
) -> Dict[str, float]:
    """
    Assess verification confidence based on similarity scores.
    
    Args:
        similarity_scores: List of similarity scores (0-1)
        match_threshold: Threshold for "match" status
        partial_threshold: Threshold for "partial" status
    
    Returns:
        Dictionary with confidence metrics
    """
    if not similarity_scores:
        return {
            "overall": 0.0,
            "match_rate": 0.0,
            "partial_rate": 0.0,
            "mismatch_rate": 0.0
        }
    
    matches = sum(1 for s in similarity_scores if s >= match_threshold)
    partials = sum(1 for s in similarity_scores if partial_threshold <= s < match_threshold)
    mismatches = len(similarity_scores) - matches - partials
    
    total = len(similarity_scores)
    
    return {
        "overall": statistics.mean(similarity_scores),
        "match_rate": matches / total,
        "partial_rate": partials / total,
        "mismatch_rate": mismatches / total
    }


"""
Text type detection (printed vs handwritten).
"""
from enum import Enum
from typing import Optional
from PIL import Image
import numpy as np
import cv2

from app.image_processing import pil_to_cv


class TextType(Enum):
    """Text type enumeration."""
    PRINTED = "printed"
    HANDWRITTEN = "handwritten"
    MIXED = "mixed"
    UNKNOWN = "unknown"


def detect_text_type(image: Image.Image, threshold: float = 0.7) -> TextType:
    """
    Detect if text in image is printed or handwritten.
    
    Uses heuristics based on:
    - Line regularity (printed text has more regular lines)
    - Character spacing (printed text has more uniform spacing)
    - Edge patterns (printed text has sharper edges)
    
    Args:
        image: PIL Image
        threshold: Confidence threshold for classification
    
    Returns:
        TextType enum value
    """
    cv_img = pil_to_cv(image)
    gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
    
    # Binarize
    _, binary = cv2.threshold(
        gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
    )
    binary = 255 - binary  # Invert
    
    # Detect horizontal lines (text lines)
    horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (40, 1))
    horizontal_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, horizontal_kernel)
    
    # Calculate line regularity
    h_proj = np.sum(horizontal_lines, axis=1)
    h_proj_nonzero = h_proj[h_proj > 0]
    
    if len(h_proj_nonzero) == 0:
        return TextType.UNKNOWN
    
    # Regularity metric: lower std = more regular (printed)
    line_spacing_std = np.std(np.diff(np.where(h_proj > 0)[0])) if len(np.where(h_proj > 0)[0]) > 1 else 0
    
    # Character spacing analysis
    vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 5))
    vertical_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, vertical_kernel)
    v_proj = np.sum(vertical_lines, axis=0)
    v_proj_nonzero = v_proj[v_proj > 0]
    
    char_spacing_std = np.std(np.diff(np.where(v_proj > 0)[0])) if len(np.where(v_proj > 0)[0]) > 1 else 0
    
    # Edge sharpness (printed text has sharper edges)
    edges = cv2.Canny(gray, 50, 150)
    edge_density = np.sum(edges > 0) / (edges.shape[0] * edges.shape[1])
    
    # Heuristic scoring
    # Lower line_spacing_std and char_spacing_std suggest printed text
    # Higher edge_density suggests printed text
    
    printed_score = 0.0
    
    if line_spacing_std < 5.0:
        printed_score += 0.3
    elif line_spacing_std < 10.0:
        printed_score += 0.15
    
    if char_spacing_std < 3.0:
        printed_score += 0.3
    elif char_spacing_std < 6.0:
        printed_score += 0.15
    
    if edge_density > 0.1:
        printed_score += 0.2
    elif edge_density > 0.05:
        printed_score += 0.1
    
    # Classify
    if printed_score >= threshold:
        return TextType.PRINTED
    elif printed_score >= threshold * 0.5:
        return TextType.MIXED
    elif printed_score > 0:
        return TextType.HANDWRITTEN
    else:
        return TextType.UNKNOWN


def detect_text_regions(image: Image.Image) -> list[tuple[int, int, int, int]]:
    """
    Detect text regions in image.
    
    Returns:
        List of (x, y, w, h) bounding boxes
    """
    cv_img = pil_to_cv(image)
    gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
    
    # Binarize
    _, binary = cv2.threshold(
        gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
    )
    binary = 255 - binary
    
    # Find contours
    contours, _ = cv2.findContours(
        binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )
    
    boxes = []
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        # Filter small regions
        if w > 10 and h > 10:
            boxes.append((x, y, w, h))
    
    return boxes


"""
Comprehensive image quality scoring for OCR.
"""
import numpy as np
import cv2
from typing import Dict
from PIL import Image

from app.image_processing import pil_to_cv
from ocr.quality.blur_detector import compute_blur_score, is_blurry

BLUR_THRESHOLD = 80.0
NOISE_THRESHOLD = 25.0
MIN_BRIGHTNESS = 60.0
MAX_BRIGHTNESS = 210.0


def compute_noise_score(image: Image.Image) -> float:
    """
    Compute noise score (higher = more noise).
    
    Args:
        image: PIL Image
    
    Returns:
        Noise score
    """
    cv_img = pil_to_cv(image)
    gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (3, 3), 0)
    noise = gray.astype("float32") - blurred.astype("float32")
    return float(noise.std())


def compute_brightness(image: Image.Image) -> float:
    """
    Compute average brightness.
    
    Args:
        image: PIL Image
    
    Returns:
        Brightness score (0-255)
    """
    cv_img = pil_to_cv(image)
    gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
    return float(gray.mean())


def detect_table_like_structure(image: Image.Image) -> bool:
    """
    Detect if image contains table-like structures.
    
    Args:
        image: PIL Image
    
    Returns:
        True if table-like structure detected
    """
    cv_img = pil_to_cv(image)
    gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)
    lines = cv2.HoughLinesP(
        edges, 1, np.pi/180, threshold=80,
        minLineLength=50, maxLineGap=5
    )
    
    if lines is None:
        return False
    
    vertical = horizontal = 0
    for line in lines:
        x1, y1, x2, y2 = line[0]
        dx = abs(x2 - x1)
        dy = abs(y2 - y1)
        if dx < 5 and dy > 20:
            vertical += 1
        elif dy < 5 and dx > 20:
            horizontal += 1
    
    return (vertical + horizontal) >= 10


def assess_image_quality(image: Image.Image) -> Dict:
    """
    Comprehensive image quality assessment.
    
    Args:
        image: PIL Image
    
    Returns:
        Dictionary with quality metrics and assessment
    """
    blur_score = compute_blur_score(image)
    noise_score = compute_noise_score(image)
    brightness_score = compute_brightness(image)
    has_table_like = detect_table_like_structure(image)
    
    # Identify issues
    issues = []
    if blur_score < BLUR_THRESHOLD:
        issues.append("blur")
    if noise_score > NOISE_THRESHOLD:
        issues.append("noise")
    if brightness_score < MIN_BRIGHTNESS:
        issues.append("dark")
    elif brightness_score > MAX_BRIGHTNESS:
        issues.append("over_exposed")
    
    # Determine quality label
    if not issues:
        quality_label = "good"
        suggest_retake = False
    elif "blur" in issues and "dark" in issues:
        quality_label = "poor"
        suggest_retake = True
    else:
        quality_label = "ok"
        suggest_retake = "blur" in issues or "dark" in issues
    
    # Calculate overall quality score (0-1)
    quality_score = 1.0
    if blur_score < BLUR_THRESHOLD:
        quality_score *= 0.5
    if noise_score > NOISE_THRESHOLD:
        quality_score *= 0.8
    if brightness_score < MIN_BRIGHTNESS or brightness_score > MAX_BRIGHTNESS:
        quality_score *= 0.7
    
    return {
        "blur_score": blur_score,
        "noise_score": noise_score,
        "brightness_score": brightness_score,
        "quality_label": quality_label,
        "quality_score": quality_score,
        "has_table_like_structure": has_table_like,
        "suggest_retake": suggest_retake,
        "issues": issues
    }


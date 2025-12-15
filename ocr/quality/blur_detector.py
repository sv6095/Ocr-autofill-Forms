"""
Blur detection for image quality assessment.
"""
import numpy as np
import cv2
from PIL import Image

from app.image_processing import pil_to_cv

BLUR_THRESHOLD = 80.0


def compute_blur_score(image: Image.Image) -> float:
    """
    Compute blur score using Laplacian variance.
    Higher score = sharper image.
    
    Args:
        image: PIL Image
    
    Returns:
        Blur score (higher is better)
    """
    cv_img = pil_to_cv(image)
    gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
    laplacian = cv2.Laplacian(gray, cv2.CV_64F)
    return float(laplacian.var())


def is_blurry(image: Image.Image, threshold: float = BLUR_THRESHOLD) -> bool:
    """
    Check if image is blurry.
    
    Args:
        image: PIL Image
        threshold: Blur threshold
    
    Returns:
        True if image is blurry
    """
    score = compute_blur_score(image)
    return score < threshold


def detect_motion_blur(image: Image.Image) -> float:
    """
    Detect motion blur using directional gradients.
    
    Args:
        image: PIL Image
    
    Returns:
        Motion blur score (0-1, higher = more motion blur)
    """
    cv_img = pil_to_cv(image)
    gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
    
    # Compute gradients in x and y directions
    gx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
    
    # Calculate gradient magnitude
    magnitude = np.sqrt(gx**2 + gy**2)
    
    # Motion blur typically shows as elongated features in one direction
    # We can use the ratio of directional gradients
    gx_mean = np.mean(np.abs(gx))
    gy_mean = np.mean(np.abs(gy))
    
    if gx_mean + gy_mean == 0:
        return 0.0
    
    # High ratio indicates directional blur
    ratio = max(gx_mean, gy_mean) / (gx_mean + gy_mean)
    return float(ratio)


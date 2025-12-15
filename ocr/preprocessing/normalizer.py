"""
Image normalization for OCR preprocessing.
"""
from PIL import Image
import numpy as np
import cv2

from app.image_processing import pil_to_cv, cv_to_pil
from app.config import DEFAULT_MAX_DIM


def deskew_image(image: Image.Image, max_skew_deg: float = 15.0) -> Image.Image:
    """
    Deskew (rotate) image to correct orientation.
    
    Args:
        image: PIL Image
        max_skew_deg: Maximum skew angle to correct
    
    Returns:
        Deskewed PIL Image
    """
    cv_img = pil_to_cv(image)
    gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
    _, bw = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    bw = 255 - bw
    
    coords = np.column_stack(np.where(bw > 0))
    if coords.shape[0] < 10:
        return image
    
    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle
    
    if abs(angle) > max_skew_deg:
        return image
    
    (h, w) = cv_img.shape[:2]
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    rotated = cv2.warpAffine(
        cv_img, M, (w, h),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_REPLICATE
    )
    
    return cv_to_pil(rotated)


def normalize_size(
    image: Image.Image,
    max_dim: int = DEFAULT_MAX_DIM,
    min_dim: int = 300
) -> Image.Image:
    """
    Normalize image size for OCR processing.
    
    Args:
        image: PIL Image
        max_dim: Maximum dimension (width or height)
        min_dim: Minimum dimension
    
    Returns:
        Resized PIL Image
    """
    w, h = image.size
    max_side = max(w, h)
    min_side = min(w, h)
    
    # Scale down if too large
    if max_side > max_dim:
        scale = max_dim / max_side
        new_w = int(w * scale)
        new_h = int(h * scale)
        image = image.resize((new_w, new_h), Image.LANCZOS)
    
    # Scale up if too small
    elif min_side < min_dim:
        scale = min_dim / min_side
        new_w = int(w * scale)
        new_h = int(h * scale)
        image = image.resize((new_w, new_h), Image.LANCZOS)
    
    return image


def binarize_image(
    image: Image.Image,
    method: str = "adaptive"
) -> Image.Image:
    """
    Binarize image (convert to black and white).
    
    Args:
        image: PIL Image
        method: Binarization method ("adaptive", "otsu", "threshold")
    
    Returns:
        Binarized PIL Image
    """
    cv_img = pil_to_cv(image)
    gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
    
    if method == "adaptive":
        binary = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 31, 10
        )
    elif method == "otsu":
        _, binary = cv2.threshold(
            gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
        )
    else:  # threshold
        _, binary = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)
    
    binary_bgr = cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)
    return cv_to_pil(binary_bgr)


def normalize_for_ocr(
    image: Image.Image,
    deskew: bool = True,
    normalize_size: bool = True,
    binarize: bool = True,
    max_dim: int = DEFAULT_MAX_DIM
) -> Image.Image:
    """
    Apply comprehensive normalization for OCR.
    
    Args:
        image: PIL Image
        deskew: Whether to deskew image
        normalize_size: Whether to normalize size
        binarize: Whether to binarize image
        max_dim: Maximum dimension for size normalization
    
    Returns:
        Normalized PIL Image
    """
    img = image.convert("RGB")
    
    if deskew:
        img = deskew_image(img)
    
    if normalize_size:
        img = normalize_size(img, max_dim=max_dim)
    
    if binarize:
        img = binarize_image(img, method="adaptive")
    
    return img


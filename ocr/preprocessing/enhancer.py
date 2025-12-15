"""
Image enhancement for OCR preprocessing.
"""
from PIL import Image, ImageEnhance
import numpy as np
import cv2

from app.image_processing import pil_to_cv, cv_to_pil


def enhance_contrast(image: Image.Image, factor: float = 1.4) -> Image.Image:
    """Enhance image contrast."""
    enhancer = ImageEnhance.Contrast(image)
    return enhancer.enhance(factor)


def enhance_sharpness(image: Image.Image, factor: float = 1.4) -> Image.Image:
    """Enhance image sharpness."""
    enhancer = ImageEnhance.Sharpness(image)
    return enhancer.enhance(factor)


def enhance_brightness(image: Image.Image, factor: float = 1.1) -> Image.Image:
    """Enhance image brightness."""
    enhancer = ImageEnhance.Brightness(image)
    return enhancer.enhance(factor)


def denoise_image(image: Image.Image, strength: int = 7) -> Image.Image:
    """
    Remove noise from image using Non-local Means Denoising.
    
    Args:
        image: PIL Image
        strength: Denoising strength (h parameter)
    
    Returns:
        Denoised PIL Image
    """
    cv_img = pil_to_cv(image)
    gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
    denoised = cv2.fastNlMeansDenoising(
        gray, None, h=strength, templateWindowSize=7, searchWindowSize=21
    )
    denoised_bgr = cv2.cvtColor(denoised, cv2.COLOR_GRAY2BGR)
    return cv_to_pil(denoised_bgr)


def enhance_for_ocr(
    image: Image.Image,
    contrast: float = 1.4,
    sharpness: float = 1.4,
    brightness: float = 1.1,
    denoise: bool = True,
    denoise_strength: int = 7
) -> Image.Image:
    """
    Apply comprehensive enhancement for OCR.
    
    Args:
        image: PIL Image
        contrast: Contrast enhancement factor
        sharpness: Sharpness enhancement factor
        brightness: Brightness enhancement factor
        denoise: Whether to apply denoising
        denoise_strength: Denoising strength
    
    Returns:
        Enhanced PIL Image
    """
    img = image.convert("RGB")
    
    if denoise:
        img = denoise_image(img, denoise_strength)
    
    img = enhance_contrast(img, contrast)
    img = enhance_sharpness(img, sharpness)
    img = enhance_brightness(img, brightness)
    
    return img


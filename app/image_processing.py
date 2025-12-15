# app/image_processing.py
"""
Image preprocessing utilities for OCR pipeline.
This version is backwards-compatible with callers that pass deprecated kwargs
like `binarize_method` or `binarize_flag`. Use the stable `binarize` bool
argument going forward.
Does NOT import other local app.* modules at top-level to avoid circular imports.
"""

from typing import Tuple, List, Any
import numpy as np
import cv2
from PIL import Image, ImageEnhance
import io

# --------------------
# Conversions
# --------------------
def pil_to_cv(img: Image.Image) -> np.ndarray:
    if img.mode == "RGBA":
        img = img.convert("RGB")
    elif img.mode == "L":
        img = img.convert("RGB")
    arr = np.array(img)
    if arr.ndim == 3 and arr.shape[2] == 3:
        # PIL is RGB, OpenCV expects BGR
        arr = arr[:, :, ::-1].copy()
    return arr

def cv_to_pil(img: np.ndarray) -> Image.Image:
    if img.ndim == 3 and img.shape[2] == 3:
        img_rgb = img[:, :, ::-1]  # BGR -> RGB
    else:
        img_rgb = img
    return Image.fromarray(img_rgb)

def open_image_bytes(data: bytes) -> Image.Image:
    return Image.open(io.BytesIO(data))

# --------------------
# Small helpers
# --------------------
def handle_transparency(pil_img: Image.Image, bg_color=(255,255,255)) -> Image.Image:
    if pil_img.mode in ("RGB", "L"):
        return pil_img.convert("RGB")
    background = Image.new("RGB", pil_img.size, bg_color)
    background.paste(pil_img, mask=pil_img.split()[3])
    return background

def sharpen_and_contrast(pil: Image.Image, sharpness=1.2, contrast=1.2) -> Image.Image:
    enhancer_s = ImageEnhance.Sharpness(pil)
    pil = enhancer_s.enhance(sharpness)
    enhancer_c = ImageEnhance.Contrast(pil)
    pil = enhancer_c.enhance(contrast)
    return pil

def upscale_region(pil: Image.Image, scale: float = 2.0, resample=Image.BICUBIC) -> Image.Image:
    w, h = pil.size
    nw = int(round(w * scale))
    nh = int(round(h * scale))
    if nw < 1 or nh < 1:
        return pil
    return pil.resize((nw, nh), resample=resample)

# --------------------
# CV preprocessing
# --------------------
def deskew_image_cv(img: np.ndarray, max_diagonal_skew_deg: float = 15.0) -> np.ndarray:
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, bw = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    bw = 255 - bw
    coords = np.column_stack(np.where(bw > 0))
    if coords.shape[0] < 10:
        return img
    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle
    if abs(angle) > max_diagonal_skew_deg:
        return img
    (h, w) = img.shape[:2]
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    rotated = cv2.warpAffine(img, M, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    return rotated

def rescale_for_model(img: np.ndarray, max_dim: int = 1600) -> np.ndarray:
    h, w = img.shape[:2]
    scale = 1.0
    if max(h, w) > max_dim:
        scale = max_dim / float(max(h, w))
    if scale == 1.0:
        return img
    new_w = int(round(w * scale))
    new_h = int(round(h * scale))
    resized = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
    return resized

def remove_noise_and_binarize(img: np.ndarray, denoise_strength: int = 7) -> np.ndarray:
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    denoised = cv2.fastNlMeansDenoising(gray, None, h=denoise_strength, templateWindowSize=7, searchWindowSize=21)
    th = cv2.adaptiveThreshold(denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 10)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1,1))
    opened = cv2.morphologyEx(th, cv2.MORPH_OPEN, kernel)
    bgr = cv2.cvtColor(opened, cv2.COLOR_GRAY2BGR)
    return bgr

def dilate_erode(img: np.ndarray, dilate_iter: int = 0, erode_iter: int = 0) -> np.ndarray:
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2,2))
    res = img.copy()
    if dilate_iter > 0:
        res = cv2.dilate(res, kernel, iterations=dilate_iter)
    if erode_iter > 0:
        res = cv2.erode(res, kernel, iterations=erode_iter)
    return res

def trim_borders(img: np.ndarray, border_px: int = 5) -> np.ndarray:
    h, w = img.shape[:2]
    top = border_px
    left = border_px
    right = w - border_px
    bottom = h - border_px
    if right <= left or bottom <= top:
        return img
    return img[top:bottom, left:right]

# --------------------
# Small text detection
# --------------------
def detect_small_text_regions(cv_img: np.ndarray, min_area=50, max_area=2000) -> List[tuple]:
    gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
    try:
        mser = cv2.MSER_create(_delta=5, _min_area=min_area, _max_area=max_area)
        regions, _ = mser.detectRegions(gray)
        boxes = []
        for r in regions:
            x,y,w,h = cv2.boundingRect(r.reshape(-1,1,2))
            if w < 6 or h < 6:
                continue
            boxes.append((x,y,w,h))
        if not boxes:
            return []
        picks = []
        for b in boxes:
            bx,by,bw,bh = b
            merged = False
            for i,p in enumerate(picks):
                px,py,pw,ph = p
                if not (bx > px+pw or px > bx+bw or by > py+ph or py > by+bh):
                    nx = min(bx, px)
                    ny = min(by, py)
                    nw = max(bx+bw, px+pw) - nx
                    nh = max(by+bh, py+ph) - ny
                    picks[i] = (nx, ny, nw, nh)
                    merged = True
                    break
            if not merged:
                picks.append((bx,by,bw,bh))
        return picks
    except Exception:
        gray = cv2.GaussianBlur(gray, (3,3), 0)
        _, th = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        th = 255 - th
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3,3))
        th = cv2.morphologyEx(th, cv2.MORPH_OPEN, kernel, iterations=1)
        contours, _ = cv2.findContours(th, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        boxes = []
        for c in contours:
            x,y,w,h = cv2.boundingRect(c)
            if w < 6 or h < 6 or w*h > 20000:
                continue
            boxes.append((x,y,w,h))
        return boxes

# --------------------
# Public pipeline (backwards-compatible)
# --------------------
def preprocess_pipeline(pil_img: Image.Image, *,
                        max_dim: int = 1600,
                        denoise_strength: int = 7,
                        deskew: bool = True,
                        binarize: bool = True,
                        dilate_iter: int = 0,
                        erode_iter: int = 0,
                        upscale_small_text: bool = True,
                        small_text_scale: float = 2.0,
                        **kwargs: Any) -> Image.Image:
    """
    Backwards-compatible preprocess pipeline.

    Accepts:
      - binarize (bool): canonical flag
      - binarize_method (str or bool): legacy alias, if string => treated as True
      - binarize_flag (bool): alias
    Any additional kwargs are ignored (but won't crash).
    """
    # Accept legacy aliases gracefully
    if "binarize_method" in kwargs:
        bm = kwargs.get("binarize_method")
        # If caller passed a string like "adaptive", treat as binarize=True
        if isinstance(bm, str):
            binarize = True
        elif isinstance(bm, bool):
            binarize = bm
        else:
            binarize = True
        # small log so you can find callers later
        try:
            print(f"[image_processing] Warning: caller passed deprecated 'binarize_method' -> mapped to binarize={binarize}")
        except Exception:
            pass
    if "binarize_flag" in kwargs:
        bf = kwargs.get("binarize_flag")
        if isinstance(bf, bool):
            binarize = bf
            try:
                print(f"[image_processing] Notice: mapped 'binarize_flag' to binarize={binarize}")
            except Exception:
                pass
    # ignore other unknown kwargs silently (for forward-compat)

    pil = handle_transparency(pil_img)
    pil = sharpen_and_contrast(pil, sharpness=1.1, contrast=1.1)
    cv = pil_to_cv(pil)

    if deskew:
        cv = deskew_image_cv(cv)

    cv = rescale_for_model(cv, max_dim=max_dim)

    if binarize:
        cv = remove_noise_and_binarize(cv, denoise_strength=denoise_strength)

    if dilate_iter or erode_iter:
        cv = dilate_erode(cv, dilate_iter=dilate_iter, erode_iter=erode_iter)

    cv = trim_borders(cv, border_px=4)

    if upscale_small_text:
        try:
            boxes = detect_small_text_regions(cv)
            if boxes:
                base_pil = cv_to_pil(cv)
                for (x,y,w,h) in boxes:
                    crop = base_pil.crop((x, y, x+w, y+h))
                    up = upscale_region(crop, scale=small_text_scale)
                    up = sharpen_and_contrast(up, sharpness=1.4, contrast=1.1)
                    try:
                        base_pil.paste(up.resize((w, h), Image.BICUBIC), (x, y))
                    except Exception:
                        continue
                return base_pil.convert("RGB")
        except Exception:
            pass

    return cv_to_pil(cv)

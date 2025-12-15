# app/table_recognition.py
"""
Detect tables and extract table cell bounding boxes.
Returns structured JSON with table bounding boxes and list of cell bboxes.
Optional OCR per cell (using pytesseract) if requested.
"""

from typing import List, Tuple, Dict
from PIL import Image
import numpy as np
import cv2
import pytesseract
from .image_processing import pil_to_cv, cv_to_pil

def detect_tables(pil_image: Image.Image, debug: bool = False) -> List[Dict]:
    """
    Detect table regions. Returns list of dicts:
      { "table_id": n, "bbox": {"x":x,"y":y,"w":w,"h":h}, "cells": [ {x,y,w,h}, ... ] }
    """
    cv_img = pil_to_cv(pil_image)
    gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
    # binarize
    _, th = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    th = 255 - th  # invert: text/table lines become white
    # morphological operations to detect vertical and horizontal lines
    scale = max(1, int(min(cv_img.shape[1], cv_img.shape[0]) / 1000))
    horiz_size = max(1, int(cv_img.shape[1] / 15))
    vert_size = max(1, int(cv_img.shape[0] / 15))
    # horizontal kernel
    horiz_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (horiz_size, 1))
    horiz_lines = cv2.morphologyEx(th, cv2.MORPH_OPEN, horiz_kernel, iterations=2)
    # vertical kernel
    vert_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, vert_size))
    vert_lines = cv2.morphologyEx(th, cv2.MORPH_OPEN, vert_kernel, iterations=2)
    # combine
    table_mask = cv2.addWeighted(horiz_lines, 0.5, vert_lines, 0.5, 0.0)
    # erode/dilate to connect
    table_mask = cv2.dilate(table_mask, np.ones((3,3), np.uint8), iterations=2)
    # find contours on mask
    contours, _ = cv2.findContours(table_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    tables = []
    table_id = 0
    for cnt in contours:
        x,y,w,h = cv2.boundingRect(cnt)
        # filter tiny regions
        if w < 50 or h < 50:
            continue
        table_roi = cv_img[y:y+h, x:x+w]
        cells = extract_cells_from_table(table_roi, offset=(x,y))
        tables.append({"table_id": table_id, "bbox": {"x":int(x),"y":int(y),"w":int(w),"h":int(h)}, "cells": cells})
        table_id += 1
    return tables

def extract_cells_from_table(cv_table_roi, offset=(0,0)) -> List[Dict]:
    """
    Given a cv2 image of a table region, detect cell bounding boxes using line intersection
    and contours. Return list of cells with absolute coordinates (x,y,w,h).
    """
    gray = cv2.cvtColor(cv_table_roi, cv2.COLOR_BGR2GRAY)
    _, th = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    th = 255 - th
    # detect horizontal and vertical lines as before
    horiz_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(1, int(cv_table_roi.shape[1]/15)), 1))
    vert_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(1, int(cv_table_roi.shape[0]/15))))
    horiz_lines = cv2.morphologyEx(th, cv2.MORPH_OPEN, horiz_kernel, iterations=2)
    vert_lines = cv2.morphologyEx(th, cv2.MORPH_OPEN, vert_kernel, iterations=2)
    mask = cv2.addWeighted(horiz_lines, 0.5, vert_lines, 0.5, 0.0)
    mask = cv2.dilate(mask, np.ones((3,3), np.uint8), iterations=1)
    # find contours within table ROI
    contours, _ = cv2.findContours(mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    cells = []
    for cnt in contours:
        x,y,w,h = cv2.boundingRect(cnt)
        # skip outer boundary (big boxes)
        if w < 15 or h < 10:
            continue
        ax = x + offset[0]
        ay = y + offset[1]
        cells.append({"x": int(ax), "y": int(ay), "w": int(w), "h": int(h)})
    # Optionally cluster / sort cells (top-to-bottom, left-to-right)
    cells_sorted = sorted(cells, key=lambda c: (c["y"], c["x"]))
    return cells_sorted

def ocr_cells_on_table(pil_image: Image.Image, cells: List[Dict], tess_lang="eng") -> List[Dict]:
    """
    Run pytesseract on each cell and attach 'text' to each cell dict.
    """
    import pytesseract
    results = []
    for c in cells:
        x,y,w,h = c["x"], c["y"], c["w"], c["h"]
        crop = pil_image.crop((x, y, x+w, y+h))
        try:
            text = pytesseract.image_to_string(crop, lang=tess_lang)
        except Exception:
            text = pytesseract.image_to_string(crop)
        c_with_text = c.copy()
        c_with_text["text"] = text.strip()
        results.append(c_with_text)
    return results

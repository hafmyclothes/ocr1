"""
ocr_engine.py — OCR ด้วย Tesseract + PyMuPDF
รองรับ PDF (text & scanned), PNG, JPG โดยไม่ใช้ Google Cloud Vision
"""
from __future__ import annotations

import io
import re
from typing import List, Tuple

from PIL import Image, ImageEnhance, ImageFilter

try:
    import fitz  # PyMuPDF
    PYMUPDF_OK = True
except ImportError:
    PYMUPDF_OK = False

try:
    import pytesseract
    TESSERACT_OK = True
except ImportError:
    TESSERACT_OK = False


# ─── Image preprocessing ─────────────────────────────────────────────────────

def preprocess_for_ocr(img: Image.Image) -> Image.Image:
    """
    ปรับปรุงคุณภาพภาพก่อน OCR
    - แปลงเป็น RGB
    - ขยายขนาดถ้าเล็กเกินไป
    - เพิ่ม contrast / sharpness
    """
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")

    w, h = img.size
    # ขยายถ้าความกว้างน้อยกว่า 1 400 px
    if w < 1400:
        scale = 1400 / w
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

    # เพิ่ม contrast
    img = ImageEnhance.Contrast(img).enhance(1.4)
    # เพิ่มความคมชัด
    img = ImageEnhance.Sharpness(img).enhance(2.0)
    return img


# ─── Tesseract OCR ────────────────────────────────────────────────────────────

def _tesseract_ocr(img: Image.Image, lang: str = "tha+eng") -> str:
    if not TESSERACT_OK:
        return "[Tesseract not available]"
    try:
        cfg = "--oem 3 --psm 6 -c preserve_interword_spaces=1"
        return pytesseract.image_to_string(img, lang=lang, config=cfg)
    except Exception as exc:
        return f"[OCR error: {exc}]"


# ─── PDF extraction ───────────────────────────────────────────────────────────

def extract_text_from_pdf(pdf_bytes: bytes, lang: str = "tha+eng") -> List[str]:
    """
    ดึงข้อความจาก PDF ทีละหน้า
    - ลองดึง text layer ก่อน
    - ถ้าหน้าว่าง → render เป็นภาพ → Tesseract OCR
    """
    if not PYMUPDF_OK:
        raise RuntimeError("PyMuPDF (fitz) ไม่ได้ติดตั้ง กรุณา pip install PyMuPDF")

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages: List[str] = []

    for page_num in range(len(doc)):
        page = doc[page_num]

        # ลอง direct text ก่อน
        direct = page.get_text("text").strip()

        if len(direct) > 20:
            pages.append(direct)
        else:
            # Render → image → OCR
            mat = fitz.Matrix(2.5, 2.5)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            img_bytes = pix.tobytes("png")
            img = Image.open(io.BytesIO(img_bytes))
            img = preprocess_for_ocr(img)
            text = _tesseract_ocr(img, lang=lang)
            pages.append(text)

    doc.close()
    return pages


# ─── Image extraction ─────────────────────────────────────────────────────────

def extract_text_from_image(img_bytes: bytes, lang: str = "tha+eng") -> str:
    """ดึงข้อความจากไฟล์ภาพ PNG/JPG"""
    img = Image.open(io.BytesIO(img_bytes))
    img = preprocess_for_ocr(img)
    return _tesseract_ocr(img, lang=lang)


# ─── Language detection ───────────────────────────────────────────────────────

def detect_primary_language(text: str) -> str:
    thai_chars = sum(1 for c in text if "\u0e00" <= c <= "\u0e7f")
    alpha_chars = sum(1 for c in text if c.isalpha())
    if alpha_chars == 0:
        return "mixed"
    ratio = thai_chars / alpha_chars
    if ratio > 0.6:
        return "thai"
    if ratio > 0.15:
        return "mixed"
    return "english"


def get_tesseract_lang(user_lang: str) -> str:
    mapping = {
        "thai": "tha",
        "english": "eng",
        "mixed": "tha+eng",
        "auto": "tha+eng",
    }
    return mapping.get(user_lang, "tha+eng")

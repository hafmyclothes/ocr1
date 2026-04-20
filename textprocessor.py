"""
text_processor.py — แก้ไขสระ / แบ่ง segment ภาษาไทยและอังกฤษ

ปัญหาสระภาษาไทยที่มักเกิดจาก OCR:
  1. สระลอย (floating vowel) — สระปรากฏโดยไม่มีพยัญชนะ
  2. วรรณยุกต์ซ้อน — วรรณยุกต์ 2 ตัวติดกัน
  3. นิคหิต + สระอา → ควรเป็นสระอำ
  4. อักษรที่ OCR อ่านผิด เช่น ภ ↔ ภ  หรือ ใ ↔ ไ
"""
from __future__ import annotations

import re
import unicodedata
from typing import List

# pythainlp
try:
    from pythainlp.util import normalize as _thai_normalize
    from pythainlp.tokenize import sent_tokenize as _thai_sent_tokenize
    PYTHAINLP_OK = True
except ImportError:
    PYTHAINLP_OK = False

# NLTK
try:
    import nltk
    for _pkg in ["punkt", "punkt_tab"]:
        try:
            nltk.data.find(f"tokenizers/{_pkg}")
        except LookupError:
            nltk.download(_pkg, quiet=True)
    from nltk.tokenize import sent_tokenize as _en_sent_tokenize
    NLTK_OK = True
except Exception:
    NLTK_OK = False


# ─── Thai vowel / tone correction ────────────────────────────────────────────

# ชุดวรรณยุกต์ที่ห้ามซ้อน
_TONE_MARKS = set("่้๊๋")
# สระบน
_VOWELS_ABOVE = set("ิีึื็ั")
# สระล่าง
_VOWELS_BELOW = set("ุู")

def _fix_overlapping_marks(text: str) -> str:
    """กำจัดวรรณยุกต์/สระที่ซ้อนกันในกลุ่มตัวอักษรเดียว"""
    result = []
    i = 0
    while i < len(text):
        ch = text[i]
        result.append(ch)
        i += 1
        # สะสม diacritics ที่ตามมา
        seen_tones: set[str] = set()
        seen_above: set[str] = set()
        seen_below: set[str] = set()
        while i < len(text) and unicodedata.category(text[i]) in ("Mn", "Mc"):
            mark = text[i]
            if mark in _TONE_MARKS:
                if mark not in seen_tones:
                    result.append(mark)
                    seen_tones.add(mark)
            elif mark in _VOWELS_ABOVE:
                if mark not in seen_above:
                    result.append(mark)
                    seen_above.add(mark)
            elif mark in _VOWELS_BELOW:
                if mark not in seen_below:
                    result.append(mark)
                    seen_below.add(mark)
            else:
                result.append(mark)
            i += 1
    return "".join(result)


# นิคหิต (ํ) + สระอา (า) → สระอำ (ำ)
_NIKHAHIT_AA_RE = re.compile(r"\u0e4d\u0e32")

# ลบ ZWS / BOM
_INVISIBLE_RE = re.compile(r"[\u200b\u200c\u200d\ufeff\u00ad]")

# ตัดช่องว่างก่อนสระบน/วรรณยุกต์ที่เกิดจาก OCR เว้นช่องว่างผิดที่
_FLOATING_VOWEL_RE = re.compile(r" ([\u0e31\u0e34-\u0e3a\u0e47-\u0e4e])")


def fix_thai_text(text: str) -> str:
    """แก้ไขปัญหาสระภาษาไทยทั้งหมด"""
    # 1. ลบอักขระล่องหน
    text = _INVISIBLE_RE.sub("", text)
    # 2. Normalise ด้วย pythainlp
    if PYTHAINLP_OK:
        text = _thai_normalize(text)
    # 3. นิคหิต + อา → อำ
    text = _NIKHAHIT_AA_RE.sub("\u0e33", text)
    # 4. สระลอย (ช่องว่างก่อนสระบน)
    text = _FLOATING_VOWEL_RE.sub(r"\1", text)
    # 5. วรรณยุกต์/สระซ้อน
    text = _fix_overlapping_marks(text)
    # 6. ช่องว่างซ้ำ
    text = re.sub(r" {2,}", " ", text)
    return text.strip()


# ─── Segmentation — Thai ──────────────────────────────────────────────────────

_THAI_SENTENCE_END = re.compile(
    r"(?<=[ก-๙ๆ])\s{2,}|(?<=[ก-๙ๆ])\n|(?<=[\.\!\?])\s+"
)

def _is_valid_segment(s: str) -> bool:
    s = s.strip()
    if len(s) < 2:
        return False
    # ไม่ใช่แค่ตัวเลข / เครื่องหมาย
    if re.fullmatch(r"[\d\s\-\.\,\:\;\(\)\[\]\{\}\/\\]+", s):
        return False
    return True


def segment_thai(text: str) -> List[str]:
    """แบ่ง segment สำหรับข้อความภาษาไทย"""
    text = fix_thai_text(text)

    # ลอง pythainlp sent_tokenize ก่อน
    if PYTHAINLP_OK:
        try:
            raw = _thai_sent_tokenize(text)
            result = [s.strip() for s in raw if _is_valid_segment(s)]
            if result:
                return result
        except Exception:
            pass

    # Fallback: แบ่งตามบรรทัดและย่อหน้า
    segments: List[str] = []
    blocks = re.split(r"\n{2,}", text)
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        lines = block.split("\n")
        buffer: List[str] = []
        for line in lines:
            line = line.strip()
            if not line:
                if buffer:
                    seg = " ".join(buffer)
                    if _is_valid_segment(seg):
                        segments.append(seg)
                    buffer = []
                continue
            # บรรทัดสั้น + ไม่ลงท้ายด้วยสระ → น่าจะเป็น header
            last_ch = line[-1] if line else ""
            if len(line) < 40 and last_ch not in "ัิีึืุูะาแโใไาๆ":
                if buffer:
                    seg = " ".join(buffer)
                    if _is_valid_segment(seg):
                        segments.append(seg)
                    buffer = []
                if _is_valid_segment(line):
                    segments.append(line)
            else:
                buffer.append(line)
        if buffer:
            seg = " ".join(buffer)
            if _is_valid_segment(seg):
                segments.append(seg)

    return segments


# ─── Segmentation — English ───────────────────────────────────────────────────

def segment_english(text: str) -> List[str]:
    """แบ่ง segment สำหรับข้อความภาษาอังกฤษ (split on full stop)"""
    text = re.sub(r"\s+", " ", text).strip()
    if NLTK_OK:
        try:
            sents = _en_sent_tokenize(text)
        except Exception:
            sents = re.split(r"(?<=[.!?])\s+", text)
    else:
        sents = re.split(r"(?<=[.!?])\s+", text)
    return [s.strip() for s in sents if _is_valid_segment(s) and len(s) > 5]


# ─── Segmentation — Mixed ─────────────────────────────────────────────────────

def _thai_ratio(s: str) -> float:
    thai = sum(1 for c in s if "\u0e00" <= c <= "\u0e7f")
    alpha = sum(1 for c in s if c.isalpha())
    return thai / max(alpha, 1)


def segment_mixed(text: str) -> List[str]:
    """แบ่ง segment สำหรับข้อความผสมไทย-อังกฤษ"""
    segments: List[str] = []
    thai_buf: List[str] = []
    en_buf: List[str] = []

    def flush_thai():
        if thai_buf:
            segments.extend(segment_thai("\n".join(thai_buf)))
            thai_buf.clear()

    def flush_en():
        if en_buf:
            segments.extend(segment_english(" ".join(en_buf)))
            en_buf.clear()

    for line in text.split("\n"):
        line = line.strip()
        if not line:
            flush_thai(); flush_en()
            continue
        if _thai_ratio(line) > 0.3:
            flush_en(); thai_buf.append(line)
        else:
            flush_thai(); en_buf.append(line)

    flush_thai(); flush_en()
    return segments


# ─── Public API ───────────────────────────────────────────────────────────────

def process_extracted_text(pages_text: List[str], lang: str = "auto") -> List[str]:
    """
    รวม text จากหลายหน้า → แบ่ง segment ตามภาษา
    lang: 'auto' | 'thai' | 'english' | 'mixed'
    """
    all_segments: List[str] = []

    for page_text in pages_text:
        page_text = page_text.strip()
        if not page_text:
            continue

        # Auto-detect
        if lang == "auto":
            detected = (
                "thai"   if _thai_ratio(page_text) > 0.55 else
                "mixed"  if _thai_ratio(page_text) > 0.1  else
                "english"
            )
        else:
            detected = lang

        if detected == "thai":
            segs = segment_thai(page_text)
        elif detected == "english":
            segs = segment_english(page_text)
        else:
            segs = segment_mixed(page_text)

        all_segments.extend(segs)

    # deduplicate while preserving order
    seen: set[str] = set()
    unique: List[str] = []
    for s in all_segments:
        key = s.strip()
        if key not in seen:
            seen.add(key)
            unique.append(s)

    return unique

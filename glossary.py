"""
glossary.py — สกัด Glossary จาก segments

ภาษาไทย:
  - tokenize ด้วย pythainlp (engine=newmm  อิงพจนานุกรม best corpus)
  - กรอง stop word และคำไวยากรณ์ออก
  - นับความถี่ → เลือกเฉพาะคำที่เกิน threshold

ภาษาอังกฤษ:
  - ตัดคำด้วย regex
  - กรอง NLTK stop words
  - นับความถี่

หมายเหตุ: pythainlp ใช้คำจาก BEST corpus ซึ่งครอบคลุมคำไทยมาตรฐาน
          และสามารถเพิ่มคำจาก orst.go.th ผ่าน custom_dict ในอนาคต
"""
from __future__ import annotations

import re
from collections import Counter
from typing import List, Tuple

# pythainlp
try:
    from pythainlp.tokenize import word_tokenize as _thai_word_tokenize
    from pythainlp.corpus.common import thai_stopwords as _thai_stopwords
    PYTHAINLP_OK = True
    _THAI_STOP: set[str] = set(_thai_stopwords())
except Exception:
    PYTHAINLP_OK = False
    _THAI_STOP: set[str] = set()

# NLTK
try:
    import nltk
    nltk.download("stopwords", quiet=True)
    from nltk.corpus import stopwords as _en_stopwords
    _EN_STOP: set[str] = set(_en_stopwords.words("english"))
except Exception:
    _EN_STOP: set[str] = set()

# ─── คำไวยากรณ์ไทยเพิ่มเติม ─────────────────────────────────────────────────
_EXTRA_THAI_STOP: set[str] = {
    "ๆ","ฯ","ฯลฯ","และ","หรือ","แต่","เพราะ","เนื่องจาก","ดัง","เช่น",
    "คือ","ว่า","ที่","ซึ่ง","อัน","จาก","ใน","ของ","โดย","กับ","ต่อ",
    "ตาม","เพื่อ","แก่","ไป","มา","ได้","จะ","ให้","ไม่","อยู่","มี",
    "เป็น","นี้","นั้น","ทุก","ทั้ง","บาง","แต่ละ","เอง","กัน","ก็",
    "แล้ว","ยัง","ถ้า","เมื่อ","หาก","เพียง","แค่","ด้วย","อีก","เกิน",
    "ราว","ประมาณ","เกือบ","ค่อนข้าง","มาก","น้อย","มากกว่า","น้อยกว่า",
    "ใช่","ไม่ใช่","ครับ","ค่ะ","นะ","สิ","ล่ะ","นะครับ","นะคะ",
    "ทำ","ทำให้","ทำการ","ดัง","เดิม","ใหม่","เพิ่ม","ลด","เริ่ม",
    "สำหรับ","เกี่ยวกับ","ประกอบ","ประกอบด้วย","รวม","รวมถึง",
    "อย่าง","อย่างไร","แบบ","แบบไหน","ไหน","อะไร","ใคร","เมื่อไร",
    "ทำไม","อย่างไรก็ตาม","นอกจากนี้","ดังนั้น","จึง","ดังกล่าว",
}

_THAI_STOP_ALL: set[str] = _THAI_STOP | _EXTRA_THAI_STOP

# กรองด้วย regex (ตัวเลข/เครื่องหมาย/สั้นเกิน)
_PUNCT_RE = re.compile(r"^[\d\s\-\.\,\!\?\(\)\[\]\{\}\/\\@#\$%\^&\*\"\']+$")


def _is_valid_thai_term(word: str, min_len: int = 2) -> bool:
    word = word.strip()
    if not word:
        return False
    if len(word) < min_len:
        return False
    if not any("\u0e00" <= c <= "\u0e7f" for c in word):
        return False
    if word in _THAI_STOP_ALL:
        return False
    if _PUNCT_RE.match(word):
        return False
    return True


def _is_valid_en_term(word: str, min_len: int = 3) -> bool:
    word = word.lower().strip()
    if len(word) < min_len:
        return False
    if word in _EN_STOP:
        return False
    if not word.isalpha():
        return False
    return True


# ─── Thai Glossary ────────────────────────────────────────────────────────────

def extract_thai_glossary(
    segments: List[str],
    min_freq: int = 2,
    min_len: int = 2,
) -> List[Tuple[str, int]]:
    if not PYTHAINLP_OK:
        return []

    counter: Counter[str] = Counter()

    for seg in segments:
        if not any("\u0e00" <= c <= "\u0e7f" for c in seg):
            continue
        tokens = _thai_word_tokenize(seg, engine="newmm", keep_whitespace=False)
        for tok in tokens:
            tok = tok.strip()
            if _is_valid_thai_term(tok, min_len=min_len):
                counter[tok] += 1

    return [(w, f) for w, f in counter.most_common() if f >= min_freq]


# ─── English Glossary ─────────────────────────────────────────────────────────

def extract_english_glossary(
    segments: List[str],
    min_freq: int = 2,
    min_len: int = 3,
) -> List[Tuple[str, int]]:
    counter: Counter[str] = Counter()

    for seg in segments:
        # ข้ามถ้าเป็นไทยเยอะ
        thai_n = sum(1 for c in seg if "\u0e00" <= c <= "\u0e7f")
        if thai_n > len(seg) * 0.4:
            continue
        words = re.findall(r"\b[a-zA-Z]+\b", seg)
        for w in words:
            w_low = w.lower()
            if _is_valid_en_term(w_low, min_len=min_len):
                counter[w_low] += 1

    return [(w, f) for w, f in counter.most_common() if f >= min_freq]


# ─── Public API ───────────────────────────────────────────────────────────────

def extract_glossary(
    segments: List[str],
    lang: str = "auto",
    min_freq: int = 2,
) -> List[Tuple[str, int]]:
    """
    สกัด glossary terms จาก segments
    คืนค่าเป็น list ของ (term, frequency) เรียงตามความถี่
    """
    if lang == "thai":
        return extract_thai_glossary(segments, min_freq=min_freq)
    if lang == "english":
        return extract_english_glossary(segments, min_freq=min_freq)

    # auto / mixed — รวมทั้งสอง
    thai_terms = extract_thai_glossary(segments, min_freq=min_freq)
    en_terms   = extract_english_glossary(segments, min_freq=min_freq)
    combined   = thai_terms + en_terms
    combined.sort(key=lambda x: x[1], reverse=True)
    return combined

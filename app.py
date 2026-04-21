import streamlit as st
import re
import csv
import uuid
import unicodedata
from io import StringIO, BytesIO
from pathlib import Path
from collections import Counter
import pythainlp
from pythainlp.tokenize import word_tokenize

# Try to import optional dependencies
try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False

try:
    from PIL import Image
    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False

try:
    import easyocr
    EASYOCR_AVAILABLE = True
except ImportError:
    EASYOCR_AVAILABLE = False

# ─── Page Config ──────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="ไทยอักษร - Thai Text Extractor",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    :root {
        --ink: #1a1410;
        --paper: #f7f3ee;
        --gold: #c8a96e;
        --rust: #c05a2a;
        --teal: #2a7a7a;
    }
    .main {
        background-color: var(--paper);
    }
    h1, h2, h3 {
        color: var(--ink);
    }
    .stButton>button {
        background-color: var(--rust);
        color: white;
        border: none;
        border-radius: 4px;
        padding: 10px 20px;
        font-weight: 600;
    }
    .stButton>button:hover {
        background-color: #a04020;
    }
</style>
""", unsafe_allow_html=True)

# ─── Thai Text Normalization ──────────────────────────────────────────────────

def normalize_thai_text(text: str) -> str:
    """
    Normalize Thai text:
    - Fix NFC unicode normalization
    - Remove stray/duplicate diacritics
    - Fix common OCR misreads
    """
    if not text:
        return text

    # NFC normalize
    text = unicodedata.normalize('NFC', text)

    # Fix common Thai misreads
    ocr_fixes = {
        'ํา': 'ำ',
        '\u0e4d\u0e32': '\u0e33',
        'เแ': 'แ',
        'เแ': 'แ',
        '่่': '่',
        '้้': '้',
        '๊๊': '๊',
        '๋๋': '๋',
        '็็': '็',
    }
    for wrong, right in ocr_fixes.items():
        text = text.replace(wrong, right)

    # Remove zero-width chars
    text = text.replace('\u200b', '').replace('\u200c', '').replace('\u200d', '')
    text = text.replace('\ufeff', '')

    # Collapse multiple spaces/newlines
    text = re.sub(r' +', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text.strip()


def split_into_segments(text: str, min_length: int = 15) -> list:
    """
    Split normalized text into translation segments.
    
    Args:
        text: Input text to split
        min_length: Minimum segment length in characters
    
    Returns:
        List of segments
    """
    # First split on double newlines (paragraph breaks)
    paragraphs = text.split('\n\n')
    
    segments = []
    
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        
        # Split on sentence boundaries (Thai sentence enders + newlines)
        # But be more conservative to avoid over-splitting
        parts = re.split(r'(?<=[\.!\?\u0e2f\u0e5a\u0e5b])\s+(?=[A-ZĀ-Ža-z\u0e00-\u0e7f])|(?<=\n)', para)
        
        current_segment = ""
        
        for part in parts:
            part = part.strip()
            if not part:
                continue
            
            # If adding this part would make segment too long, save current and start new
            if current_segment and len(current_segment) > 200:
                if len(current_segment) >= min_length:
                    segments.append(current_segment.strip())
                current_segment = part
            else:
                # Accumulate parts
                if current_segment:
                    current_segment += " " + part
                else:
                    current_segment = part
        
        # Don't forget the last segment
        if current_segment and len(current_segment) >= min_length:
            segments.append(current_segment.strip())
    
    # Merge very short segments with previous ones
    merged_segments = []
    i = 0
    while i < len(segments):
        seg = segments[i]
        
        # If segment is too short and there's a previous segment, merge
        if len(seg) < min_length and merged_segments:
            merged_segments[-1] = merged_segments[-1] + " " + seg
        else:
            merged_segments.append(seg)
        
        i += 1
    
    return merged_segments


def extract_glossary(segments: list, top_n: int = 50, min_len: int = 2, min_freq: int = 2) -> dict:
    """Extract frequently repeated words/phrases for both Thai and English."""
    thai_char = re.compile(r'[\u0e00-\u0e7f]')
    eng_char = re.compile(r'[a-zA-Z]')
    
    thai_tokens = []
    eng_tokens = []
    
    for seg in segments:
        # Thai tokenization
        tokens = word_tokenize(seg, engine='newmm', keep_whitespace=False)
        for tok in tokens:
            tok = tok.strip()
            if len(tok) >= min_len:
                if thai_char.search(tok) and tok not in ('ๆ', 'ฯ', 'และ', 'หรือ', 'ใน', 'ที่', 'ของ', 'การ',
                                         'ให้', 'เป็น', 'ได้', 'จาก', 'โดย', 'มี', 'กับ'):
                    thai_tokens.append(tok)
        
        # English tokenization (simple word split)
        eng_words = re.findall(r'\b[a-zA-Z]{' + str(min_len) + r',}\b', seg)
        for word in eng_words:
            word_lower = word.lower()
            if word_lower not in ('the', 'and', 'or', 'in', 'to', 'of', 'a', 'is', 'for', 'on', 'with', 
                                   'as', 'at', 'by', 'from', 'it', 'be', 'this', 'that', 'was', 'are'):
                eng_tokens.append(word_lower)
    
    thai_freq = Counter(thai_tokens)
    eng_freq = Counter(eng_tokens)
    
    thai_glossary = [
        {"term": term, "frequency": count, "translation": "", "language": "Thai"}
        for term, count in thai_freq.most_common(top_n)
        if count >= min_freq
    ]
    
    eng_glossary = [
        {"term": term, "frequency": count, "translation": "", "language": "English"}
        for term, count in eng_freq.most_common(top_n)
        if count >= min_freq
    ]
    
    return {
        "thai": thai_glossary,
        "english": eng_glossary,
        "combined": sorted(thai_glossary + eng_glossary, key=lambda x: x["frequency"], reverse=True)[:top_n]
    }


def extract_from_pdf(file_bytes: bytes) -> str:
    """Extract text from PDF - text layer only (no OCR)."""
    if not PYMUPDF_AVAILABLE:
        st.error("PyMuPDF not installed. Install: pip install PyMuPDF")
        return ""

    doc = fitz.open(stream=file_bytes, filetype="pdf")
    full_text_parts = []

    for page in doc:
        text = page.get_text("text")
        if text.strip():
            full_text_parts.append(text)

    doc.close()
    return "\n\n".join(full_text_parts)


@st.cache_resource
def load_ocr_reader():
    """Load EasyOCR reader (cached for performance)."""
    try:
        return easyocr.Reader(['th', 'en'])
    except Exception as e:
        st.error(f"Failed to load OCR: {str(e)}")
        return None


def extract_from_image(file_bytes: bytes) -> str:
    """Extract text from image using EasyOCR."""
    if not PILLOW_AVAILABLE:
        st.error("Pillow not installed")
        return ""
    
    if not EASYOCR_AVAILABLE:
        st.warning("""
        ⚠️ EasyOCR ไม่พร้อมใช้งาน
        
        **สำหรับการ OCR รูปภาพ:**
        1. รัน local: `pip install easyocr`
        2. Streamlit Cloud: เพิ่ม `easyocr>=1.7.0` ใน requirements.txt
        
        **ชั่วคราว:** ใช้ PDF แทนรูปภาพ
        """)
        return ""
    
    try:
        # Import numpy only when needed
        try:
            import numpy as np
        except ImportError:
            st.error("NumPy not installed (required by EasyOCR)")
            return ""
        
        # Load image
        img = Image.open(BytesIO(file_bytes))
        
        # Convert to numpy array
        img_array = np.array(img)
        
        # Load reader
        reader = load_ocr_reader()
        if reader is None:
            return ""
        
        # Extract text
        st.info("🔄 กำลังประมวลผล OCR... (ครั้งแรกจะใช้เวลาสักครู่)")
        results = reader.readtext(img_array, detail=0)
        
        # Combine results
        text = "\n".join(results)
        return text
    
    except Exception as e:
        st.error(f"❌ OCR failed: {str(e)}")
        return ""


def segments_to_csv(segments: list, filename: str) -> str:
    """Generate CAT-tool-ready CSV from segments."""
    output = StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_ALL)
    writer.writerow(["ID", "Source (TH)", "Target", "Notes"])
    for i, seg in enumerate(segments, 1):
        writer.writerow([f"{filename}_{i:04d}", seg, "", ""])
    return output.getvalue()


def glossary_to_csv(glossary_dict: dict) -> str:
    """Generate glossary CSV for both languages."""
    output = StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_ALL)
    writer.writerow(["Term", "Language", "Frequency", "Translation", "Notes"])
    
    for item in glossary_dict["combined"]:
        writer.writerow([
            item["term"], 
            item["language"],
            item["frequency"], 
            item.get("translation", ""), 
            ""
        ])
    
    return output.getvalue()


# ─── Streamlit App ───────────────────────────────────────────────────────────

st.markdown("""
# 📄 ไทยอักษร · Thai Text Extractor

สกัดข้อความ **ไทย + อังกฤษ** จาก PDF พร้อมสร้าง Glossary สำหรับนักแปล
""")

st.info("✨ สกัดข้อความและสร้าง Glossary สำหรับ CAT Tools | สนับสนุนไทย + อังกฤษ")

# Sidebar
with st.sidebar:
    st.markdown("### ⚙️ ตั้งค่า")
    
    st.markdown("**📏 การแบ่ง Segments**")
    min_segment_length = st.slider(
        "ความยาวต่ำสุด (ตัวอักษร)", 
        5, 50, 15,
        help="Segments ที่สั้นกว่านี้จะถูกรวมเข้ากับ segment ก่อนหน้า"
    )
    
    st.markdown("**📚 Glossary**")
    top_n_glossary = st.slider("จำนวนคำในคลังศัพท์", 10, 100, 50)
    min_frequency = st.slider("ความถี่ต่ำสุด", 1, 10, 2)
    
    st.markdown("---")
    st.markdown("### 📊 สถานะ")
    
    if PYMUPDF_AVAILABLE:
        st.success("✅ PyMuPDF (PDF extraction)")
    else:
        st.error("❌ PyMuPDF (PDF extraction)")
    
    if EASYOCR_AVAILABLE:
        st.success("✅ EasyOCR (Image OCR - ไทย + อังกฤษ)")
    else:
        st.warning("⚠️ EasyOCR ไม่พร้อม")
        with st.expander("💡 ต้องการ OCR รูปภาพ?"):
            st.markdown("""
            **วิธีเปิดใช้:**
            1. Local: `pip install easyocr`
            2. Streamlit Cloud: เพิ่มใน requirements.txt
            
            **หมายเหตุ:** 
            - ดาวน์โหลดโมเดล ~100MB
            - ครั้งแรกใช้เวลา 2-3 นาที
            """)

# Main interface
col1, col2 = st.columns([1, 1])

with col1:
    st.markdown("### 📁 อัปโหลดไฟล์")
    
    if EASYOCR_AVAILABLE:
        st.markdown("> รองรับ: **PDF, PNG, JPG, JPEG, WEBP**")
        supported_types = ["pdf", "png", "jpg", "jpeg", "webp"]
    else:
        st.markdown("> รองรับ: **PDF** (text-based)")
        st.info("💡 ต้องการ PNG/JPG? ติดตั้ง: `pip install easyocr`")
        supported_types = ["pdf"]
    
    uploaded_file = st.file_uploader(
        "เลือกไฟล์", 
        type=supported_types,
        help="PDF (text-based) หรือรูปภาพ (ใช้ EasyOCR)"
    )

with col2:
    st.markdown("### ℹ️ วิธีใช้")
    st.markdown("""
    1. อัปโหลด **PDF**
    2. ระบบจะสกัดข้อความและแบ่งเป็น segments
    3. สกัดคำไทย + อังกฤษที่พบซ้ำบ่อย
    4. ดาวน์โหลด CSV ไปใน CAT Tools
    
    **หมายเหตุ:** PDF ต้องเป็น text-based (มีข้อความ ไม่ใช่รูปภาพ)
    """)

# Processing
if uploaded_file is not None:
    st.markdown("---")
    st.markdown("### 🔄 กำลังประมวลผล...")
    
    # Read file
    file_bytes = uploaded_file.read()
    filename = Path(uploaded_file.name).stem
    
    try:
        # Extract text
        progress_bar = st.progress(0)
        file_ext = Path(uploaded_file.name).suffix.lower()
        
        if file_ext == '.pdf':
            st.info("📖 สกัดข้อความจาก PDF...")
            raw_text = extract_from_pdf(file_bytes)
        elif file_ext in ['.png', '.jpg', '.jpeg', '.webp']:
            st.info("🖼️ ใช้ EasyOCR สกัดข้อความจากรูปภาพ...")
            raw_text = extract_from_image(file_bytes)
        else:
            st.error(f"❌ ไม่รองรับไฟล์นามสกุล {file_ext}")
            st.stop()
        
        progress_bar.progress(20)
        
        if not raw_text.strip():
            st.error("❌ ไม่พบข้อความในไฟล์ PDF")
            st.info("💡 ตรวจสอบว่า PDF เป็น text-based (มีข้อความ) ไม่ใช่ scanned")
            st.stop()
        
        # Normalize
        st.info("🔤 ทำให้ข้อความเป็นมาตรฐาน...")
        normalized = normalize_thai_text(raw_text)
        progress_bar.progress(40)
        
        # Split segments
        st.info("✂️ แบ่งประโยค...")
        segments = split_into_segments(normalized, min_length=min_segment_length)
        progress_bar.progress(60)
        
        if not segments:
            st.error("❌ ไม่พบข้อความหลังการประมวลผล")
            st.stop()
        
        # Extract glossary (both Thai and English)
        st.info("📚 สกัดคลังศัพท์ (ไทย + อังกฤษ)...")
        glossary = extract_glossary(segments, top_n=top_n_glossary, min_freq=min_frequency)
        progress_bar.progress(100)
        
        st.success("✅ สำเร็จ!")
        
        # Display results
        st.markdown("---")
        st.markdown("### 📊 ผลลัพธ์")
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("📝 Segments", len(segments))
        with col2:
            st.metric("🇹🇭 คำไทย", len(glossary["thai"]))
        with col3:
            st.metric("🇬🇧 คำอังกฤษ", len(glossary["english"]))
        with col4:
            st.metric("🔤 ตัวอักษร", len(normalized))
        
        # Raw preview
        with st.expander("👁️ ดูข้อความเต็ม (2000 ตัวอักษร)"):
            st.text(normalized[:2000])
        
        # Segments preview
        st.markdown("### 📖 Segments Preview (100 รายการแรก)")
        
        seg_df_data = {
            "ID": [f"{filename}_{i:04d}" for i in range(1, min(101, len(segments) + 1))],
            "ข้อความ": segments[:100],
        }
        
        st.dataframe(seg_df_data, use_container_width=True, height=400)
        
        # Glossary table with tabs
        st.markdown("### 📚 Glossary (คำซ้ำบ่อย)")
        
        tab1, tab2, tab3 = st.tabs(["🌐 ทั้งหมด", "🇹🇭 ภาษาไทย", "🇬🇧 ภาษาอังกฤษ"])
        
        with tab1:
            if glossary["combined"]:
                glo_df_data = {
                    "คำศัพท์": [g["term"] for g in glossary["combined"]],
                    "ภาษา": [g["language"] for g in glossary["combined"]],
                    "ความถี่": [g["frequency"] for g in glossary["combined"]],
                    "คำแปล": ["" for _ in glossary["combined"]],
                }
                st.dataframe(glo_df_data, use_container_width=True, height=400)
            else:
                st.info("ไม่พบคำศัพท์")
        
        with tab2:
            if glossary["thai"]:
                thai_df_data = {
                    "คำศัพท์": [g["term"] for g in glossary["thai"]],
                    "ความถี่": [g["frequency"] for g in glossary["thai"]],
                    "คำแปล": ["" for _ in glossary["thai"]],
                }
                st.dataframe(thai_df_data, use_container_width=True, height=400)
            else:
                st.info("ไม่พบคำศัพท์ภาษาไทย")
        
        with tab3:
            if glossary["english"]:
                eng_df_data = {
                    "Term": [g["term"] for g in glossary["english"]],
                    "Frequency": [g["frequency"] for g in glossary["english"]],
                    "Translation": ["" for _ in glossary["english"]],
                }
                st.dataframe(eng_df_data, use_container_width=True, height=400)
            else:
                st.info("No English terms found")
        
        # Download buttons
        st.markdown("---")
        st.markdown("### ⬇️ ดาวน์โหลด")
        
        col1, col2 = st.columns(2)
        
        with col1:
            seg_csv = segments_to_csv(segments, filename)
            st.download_button(
                label="📥 ดาวน์โหลด segments.csv (CAT Import)",
                data=seg_csv.encode('utf-8-sig'),
                file_name="segments.csv",
                mime="text/csv",
                key="download_segments"
            )
        
        with col2:
            glo_csv = glossary_to_csv(glossary)
            st.download_button(
                label="📥 ดาวน์โหลด glossary.csv (Term Base)",
                data=glo_csv.encode('utf-8-sig'),
                file_name="glossary.csv",
                mime="text/csv",
                key="download_glossary"
            )
        
        # Statistics
        with st.expander("📈 สถิติเพิ่มเติม"):
            thai_count = len(glossary["thai"])
            eng_count = len(glossary["english"])
            top_thai = glossary["thai"][0] if glossary["thai"] else None
            top_eng = glossary["english"][0] if glossary["english"] else None
            
            st.markdown(f"""
            - **จำนวน segments:** {len(segments)}
            - **คำศัพท์ภาษาไทย:** {thai_count}
            - **คำศัพท์ภาษาอังกฤษ:** {eng_count}
            - **ตัวอักษรทั้งหมด:** {len(normalized)}
            - **เฉลี่ยตัวอักษร/segment:** {len(normalized) / len(segments):.1f}
            - **คำไทยที่พบบ่อยสุด:** {top_thai['term'] if top_thai else 'N/A'} ({top_thai['frequency'] if top_thai else 'N/A'} ครั้ง)
            - **คำอังกฤษที่พบบ่อยสุด:** {top_eng['term'] if top_eng else 'N/A'} ({top_eng['frequency'] if top_eng else 'N/A'} ครั้ง)
            """)
    
    except Exception as e:
        st.error(f"❌ เกิดข้อผิดพลาด: {str(e)}")
        st.info("💡 ตรวจสอบว่า PDF เป็น text-based และมีข้อความ")

# Footer
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #7a6e60; font-size: 12px;">
    <p>ไทยอักษร · Thai Text Extractor v2.1</p>
    <p>Powered by PyThaiNLP · PyMuPDF · Streamlit</p>
    <p><a href="https://github.com/hafmyclothes/thai-text-extractor">GitHub Repository</a></p>
</div>
""", unsafe_allow_html=True)

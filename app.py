from __future__ import annotations
import io
import os
import json
import pandas as pd
import streamlit as st
from datetime import datetime

# ── Import Modules ──────────────────────────────────────────────────────────
from database import init_db, get_user_projects, get_user_stats, get_project_segments, get_project_glossary, save_project, delete_project
from auth import login_user, register_user
from ocr_engine import extract_text_from_pdf, extract_text_from_image, get_tesseract_lang
from text_processor import process_extracted_text
from glossary import extract_glossary

# ── Config & CSS ──────────────────────────────────────────────────────────────
st.set_page_config(page_title="Thai Text Extractor", page_icon="🇹🇭", layout="wide")
init_db()

# Session state initialization
for k, v in {"user": None, "page": "upload", "result": None}.items():
    if k not in st.session_state: st.session_state[k] = v

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Sarabun:wght@300;400;700&display=swap');
html, body, [class*="css"] { font-family: 'Sarabun', sans-serif !important; }
.hero { background: linear-gradient(135deg, #0f172a 0%, #1d4ed8 100%); border-radius: 20px; padding: 2rem; color: #fff; margin-bottom: 2rem; box-shadow: 0 10px 30px rgba(29,78,216,0.3); }
.card { background: #fff; border-radius: 14px; padding: 1.5rem; box-shadow: 0 2px 12px rgba(0,0,0,0.07); border: 1px solid #e2e8f0; margin-bottom: 1rem; }
.seg { background: #f8fafc; border-left: 4px solid #1d4ed8; padding: 10px; margin-bottom: 5px; border-radius: 5px; }
[data-testid="stSidebar"] { background: #0f172a !important; }
[data-testid="stSidebar"] * { color: #fff !important; }
</style>
""", unsafe_allow_html=True)

# ── Helpers ──────────────────────────────────────────────────────────────────
LANG_MAP = {"🤖 ตรวจสอบอัตโนมัติ": "auto", "🇹🇭 ภาษาไทย": "thai", "🇬🇧 ภาษาอังกฤษ": "english"}
def hero(title, subtitle):
    st.markdown(f'<div class="hero"><h1>{title}</h1><p>{subtitle}</p></div>', unsafe_allow_html=True)

# ── Page: Upload (FIXED BUTTON LOGIC) ────────────────────────────────────────
def page_upload():
    hero("📤 อัปโหลดและถอดข้อความ", "ถอดข้อความจากไฟล์ภาพและ PDF เป็น Segments พร้อมแปล")

    col_form, col_info = st.columns([3, 1], gap="large")
    with col_form:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        uploaded = st.file_uploader("ลากวางหรือเลือกไฟล์", type=["pdf", "png", "jpg", "jpeg"])
        proj_name = st.text_input("ชื่อโปรเจกต์", value=f"Project_{datetime.now().strftime('%Y%m%d_%H%M')}")
        lang_choice = st.selectbox("ภาษา", list(LANG_MAP.keys()))
        min_freq = st.slider("Glossary Freq", 1, 10, 2)
        st.markdown('</div>', unsafe_allow_html=True)

        extract_btn = st.button("🚀 เริ่มถอดข้อความ", use_container_width=True, disabled=(uploaded is None))

        # ส่วนประมวลผล
        if extract_btn and uploaded:
            with st.spinner("กำลังถอดข้อความ..."):
                try:
                    lang = LANG_MAP[lang_choice]
                    file_bytes = uploaded.read()
                    ftype = uploaded.name.split(".")[-1].lower()
                    
                    # 1. OCR
                    pages_text = extract_text_from_pdf(file_bytes, lang=get_tesseract_lang(lang)) if ftype == "pdf" else [extract_text_from_image(file_bytes, lang=get_tesseract_lang(lang))]
                    # 2. Process & Save
                    segments = process_extracted_text(pages_text, lang=lang)
                    glossary = extract_glossary(segments, lang=lang, min_freq=min_freq)
                    pid = save_project(st.session_state.user["id"], proj_name, uploaded.name, ftype, lang, segments, glossary)
                    
                    # เก็บผลลัพธ์เข้า Session
                    st.session_state.result = {"project_id": pid, "project_name": proj_name, "segments": segments, "glossary": glossary, "language": lang}
                    st.success(f"ถอดข้อความสำเร็จ! พบ {len(segments)} segments")
                except Exception as e:
                    st.error(f"เกิดข้อผิดพลาด: {e}")

        # --- จุดที่แก้ไข: ปุ่มนำทางที่แยกออกมาให้กดได้ตลอดหลังประมวลผลเสร็จ ---
        if st.session_state.result:
            st.markdown('<div style="margin-top:20px;"></div>', unsafe_allow_html=True)
            c1, c2 = st.columns(2)
            with c1:
                if st.button("📋 ดูผลลัพธ์ที่ถอดเสร็จแล้ว →", use_container_width=True, type="primary"):
                    st.session_state.page = "results"
                    st.rerun()
            with c2:
                if st.button("📚 ดู Glossary →", use_container_width=True):
                    st.session_state.page = "glossary"
                    st.rerun()

# ── Page: Results ─────────────────────────────────────────────────────────────
def page_results():
    hero("📋 ผลลัพธ์", "ตรวจสอบและดาวน์โหลดข้อมูล")
    res = st.session_state.result
    if not res: 
        st.warning("ไม่มีข้อมูล")
        return
    
    st.subheader(f"Project: {res['project_name']}")
    df = pd.DataFrame({"Segment_ID": [f"SEG_{i+1:03d}" for i in range(len(res['segments']))], "Content": res['segments']})
    st.dataframe(df, use_container_width=True)
    
    csv = df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
    st.download_button("⬇️ ดาวน์โหลด CSV", data=csv, file_name=f"{res['project_name']}.csv", mime="text/csv")

# ── Sidebar & Router ─────────────────────────────────────────────────────────
def show_sidebar():
    with st.sidebar:
        st.title("🇹🇭 Thai Extractor")
        st.write(f"👤 {st.session_state.user['username']}")
        if st.button("📤 อัปโหลดใหม่", use_container_width=True): 
            st.session_state.page = "upload"
            st.rerun()
        if st.button("📋 ดูผลลัพธ์", use_container_width=True): 
            st.session_state.page = "results"
            st.rerun()
        st.divider()
        if st.button("🚪 ออกจากระบบ", use_container_width=True, type="secondary"):
            st.session_state.user = None
            st.rerun()

def main():
    if not st.session_state.user:
        # จำลองการ Login เพื่อให้ใช้งานหน้า Upload ได้ทันที
        st.session_state.user = {"id": 1, "username": "User"}
        st.rerun()
    
    show_sidebar()
    if st.session_state.page == "results": page_results()
    else: page_upload()

if __name__ == "__main__":
    main()

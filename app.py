import pandas as pd
import streamlit as st
from datetime import datetime

# --- Import Modules ---
from database import init_db, get_user_projects, get_project_segments, save_project
from ocr_engine import extract_text_from_pdf, extract_text_from_image
from text_processor import process_extracted_text
from glossary import extract_glossary

# --- Setup ---
st.set_page_config(page_title="Thai Text Extractor", page_icon="🇹🇭", layout="wide")
init_db()

# Session State สำหรับควบคุมหน้าจอ
if "user" not in st.session_state: st.session_state.user = {"id": 1, "username": "User"}
if "page" not in st.session_state: st.session_state.page = "upload"
if "result" not in st.session_state: st.session_state.result = None

# --- Sidebar (เมนูซ้ายมือ) ---
with st.sidebar:
    st.title("🇹🇭 Menu")
    if st.button("📤 อัปโหลดใหม่", use_container_width=True): 
        st.session_state.page = "upload"
        st.rerun()
    if st.button("📁 ประวัติโปรเจกต์", use_container_width=True): 
        st.session_state.page = "history"
        st.rerun()
    st.divider()
    if st.button("🚪 ออกจากระบบ", use_container_width=True): 
        st.session_state.user = None
        st.rerun()

# --- Page Logic ---

# 1. หน้าสำหรับอัปโหลดไฟล์ (ที่เคยหายไป)
if st.session_state.page == "upload":
    st.markdown("## 📤 อัปโหลดและถอดข้อความ")
    
    with st.container():
        uploaded = st.file_uploader("ลากวางหรือคลิกเพื่อเลือกไฟล์ (PDF, PNG, JPG)", type=["pdf", "png", "jpg", "jpeg"])
        proj_name = st.text_input("ชื่อโปรเจกต์", value=f"Project_{datetime.now().strftime('%Y%m%d_%H%M')}")
        lang_choice = st.selectbox("ภาษาของเนื้อหา", ["🇹🇭 ภาษาไทย", "🇬🇧 ภาษาอังกฤษ"])
        
        extract_btn = st.button("🚀 เริ่มถอดข้อความ", use_container_width=True, disabled=(uploaded is None))

    if extract_btn and uploaded:
        with st.spinner("กำลังประมวลผล..."):
            file_bytes = uploaded.read()
            ftype = uploaded.name.split(".")[-1].lower()
            lang = "thai" if "ไทย" in lang_choice else "english"
            
            # ดำเนินการ OCR
            pages_text = extract_text_from_pdf(file_bytes, lang="tha+eng") if ftype=="pdf" else [extract_text_from_image(file_bytes, lang="tha+eng")]
            segments = process_extracted_text(pages_text, lang=lang)
            glossary = extract_glossary(segments, lang=lang)
            
            # บันทึกลง Database (เพื่อให้เรียกดูภายหลังได้)
            save_project(st.session_state.user["id"], proj_name, uploaded.name, ftype, lang, segments, glossary)
            
            # เก็บค่าไว้โชว์ในหน้า Results
            st.session_state.result = {"name": proj_name, "segments": segments}
            st.success(f"ถอดข้อความสำเร็จ! พบ {len(segments)} segments")
            
            if st.button("📋 ดูผลลัพธ์"):
                st.session_state.page = "results"
                st.rerun()

# 2. หน้าประวัติ (สำหรับดูของเก่า)
elif st.session_state.page == "history":
    st.markdown("## 📁 ประวัติโปรเจกต์")
    projects = get_user_projects(st.session_state.user["id"])
    
    if not projects:
        st.info("ยังไม่มีข้อมูลบันทึกไว้")
    else:
        for p in projects:
            col1, col2 = st.columns([4, 1])
            col1.write(f"📦 **{p['name']}** | {p['created_at']}")
            if col2.button("เปิดดู", key=f"btn_{p['id']}"):
                # ดึงข้อมูลเก่าจาก DB มาใส่ในหน้าแสดงผล
                segs = get_project_segments(p['id'])
                st.session_state.result = {"name": p['name'], "segments": [s['source_text'] for s in segs]}
                st.session_state.page = "results"
                st.rerun()

# 3. หน้าแสดงผลลัพธ์
elif st.session_state.page == "results":
    if st.session_state.result:
        st.markdown(f"### 📊 ผลลัพธ์: {st.session_state.result['name']}")
        df = pd.DataFrame(st.session_state.result['segments'], columns=["เนื้อหาที่ถอดได้"])
        st.dataframe(df, use_container_width=True)
        
        if st.button("⬅️ กลับหน้าหลัก"):
            st.session_state.page = "upload"
            st.rerun()

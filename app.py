from __future__ import annotations
import io
import os
import json
import pandas as pd
import streamlit as st
from datetime import datetime

# ── Import Modules (ต้องมั่นใจว่าไฟล์เหล่านี้อยู่ในโฟลเดอร์เดียวกัน) ──
from database import init_db, get_user_projects, get_user_stats, get_project_segments, get_project_glossary, save_project, delete_project
from auth import login_user, register_user
from ocr_engine import extract_text_from_pdf, extract_text_from_image, get_tesseract_lang
from text_processor import process_extracted_text
from glossary import extract_glossary

# ── Setup ──
st.set_page_config(page_title="Thai Text Extractor", page_icon="🇹🇭", layout="wide")
init_db()

if "user" not in st.session_state: st.session_state.user = {"id": 1, "username": "User"} # จำลอง Login
if "page" not in st.session_state: st.session_state.page = "upload"
if "result" not in st.session_state: st.session_state.result = None

# ── CSS ──
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Sarabun:wght@300;400;700&display=swap');
    html, body, [class*="css"] { font-family: 'Sarabun', sans-serif !important; }
    .hero { background: linear-gradient(135deg, #0f172a 0%, #1e3a5f 100%); border-radius: 15px; padding: 2rem; color: #fff; margin-bottom: 2rem; }
    .card { background: #fff; border-radius: 12px; padding: 1.5rem; box-shadow: 0 4px 6px rgba(0,0,0,0.05); border: 1px solid #eee; margin-bottom: 1rem; }
</style>
""", unsafe_allow_html=True)

# ── Sidebar ──
def show_sidebar():
    with st.sidebar:
        st.title("🇹🇭 Menu")
        st.divider()
        if st.button("📤 อัปโหลดใหม่", use_container_width=True): 
            st.session_state.page = "upload"; st.rerun()
        if st.button("📁 ประวัติโปรเจกต์", use_container_width=True): 
            st.session_state.page = "history"; st.rerun()
        st.divider()
        if st.button("🚪 ออกจากระบบ", use_container_width=True): 
            st.session_state.user = None; st.rerun()

# ── Page: History (แก้ไขให้ดึงของเก่าได้จริง) ──
def page_history():
    st.markdown('<div class="hero"><h1>📁 ประวัติโปรเจกต์</h1><p>รายการที่คุณเคยบันทึกไว้ในฐานข้อมูล</p></div>', unsafe_allow_html=True)
    
    # ดึงข้อมูลจากฐานข้อมูลจริง
    projects = get_user_projects(st.session_state.user["id"])
    
    if not projects:
        st.info("ยังไม่มีบันทึกเก่าในระบบ")
        return

    for proj in projects:
        with st.container():
            st.markdown(f'''<div class="card">
                <h3>📦 {proj["name"]}</h3>
                <p>ไฟล์: {proj["file_name"]} | วันที่: {proj["created_at"]}</p>
            </div>''', unsafe_allow_html=True)
            
            col1, col2 = st.columns([1, 4])
            with col1:
                if st.button("📂 เปิดดู", key=f"open_{proj['id']}", use_container_width=True):
                    # โหลดข้อมูล Segments และ Glossary จาก DB มาใส่ Session
                    segs = get_project_segments(proj['id'])
                    glss = get_project_glossary(proj['id'])
                    st.session_state.result = {
                        "project_id": proj['id'],
                        "project_name": proj['name'],
                        "segments": [s["source_text"] for s in segs],
                        "glossary": [(g["term"], g["frequency"]) for g in glss],
                        "language": proj['language']
                    }
                    st.session_state.page = "results"
                    st.rerun()
            st.divider()

# ── Main Router ──
def main():
    if not st.session_state.user:
        st.warning("Please login first")
        return
    
    show_sidebar()
    
    if st.session_state.page == "history":
        page_history()
    elif st.session_state.page == "results":
        # หน้าแสดงผลลัพธ์ (โค้ดเดียวกับที่เคยให้)
        from app_pages import page_results # สมมติว่าแยกไว้ หรือเขียนฟังก์ชันไว้ด้านล่าง
        # เพื่อความง่าย ผมรวมไว้ในเงื่อนไขนี้เลย
        st.header(f"Project: {st.session_state.result['project_name']}")
        st.table(st.session_state.result['segments'])
    else:
        # หน้า Upload เดิม (โค้ดเดียวกับที่เคยให้)
        st.markdown('<div class="hero"><h1>📤 อัปโหลดไฟล์</h1></div>', unsafe_allow_html=True)
        # ... (ส่วนของ file_uploader และ extract_btn) ...
        # มั่นใจว่าใน extract_btn มีการสั่ง save_project() ลง DB แล้ว

if __name__ == "__main__":
    main()

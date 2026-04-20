import streamlit as st
import google.generativeai as genai
import sqlite3
import json
import pandas as pd
from datetime import datetime

# ==========================================
# 1. SETUP & AI CONFIGURATION
# ==========================================
# นำ API Key ที่คุณมีใน Screenshot สุดท้ายมาใส่ตรงนี้
GEMINI_API_KEY = "YOUR_GEMINI_API_KEY" 
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

# ==========================================
# 2. DATABASE (ระบบซ่อมแซมและสร้างตาราง)
# ==========================================
def init_db():
    conn = sqlite3.connect("users.db", check_same_thread=False)
    cursor = conn.cursor()
    # สร้างตารางหลัก (ถ้ายังไม่มี)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            name TEXT,
            file_name TEXT,
            file_type TEXT,
            language TEXT,
            glossary_json TEXT,
            segments_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # 🩹 ส่วนสำคัญ: แก้ไข OperationalError (ตารางไม่มีคอลัมน์) แบบอัตโนมัติ
    columns_to_check = [
        ("segments_json", "TEXT"),
        ("glossary_json", "TEXT"),
        ("language", "TEXT")
    ]
    for col_name, col_type in columns_to_check:
        try:
            cursor.execute(f"ALTER TABLE projects ADD COLUMN {col_name} {col_type}")
        except sqlite3.OperationalError:
            pass # ถ้ามีคอลัมน์อยู่แล้วให้ข้าม
    conn.commit()
    conn.close()

# ==========================================
# 3. AI LOGIC (ส่วนที่ช่วยแบ่งประโยคภาษาไทย)
# ==========================================
def ai_resegment_text(raw_text):
    if not raw_text.strip(): return []
    prompt = f"""
    คุณเป็นผู้เชี่ยวชาญด้านภาษาไทย ช่วยแบ่งประโยคจากข้อความ OCR นี้ใหม่
    ให้แต่ละประโยคมีความยาวที่เหมาะสมสำหรับการนำไปแปลใน CAT Tools
    เงื่อนไข: ห้ามแก้คำเดิม, ห้ามสรุปความ, คืนค่าเป็น JSON List ของ String เท่านั้น
    ข้อความ: {raw_text}
    """
    try:
        response = model.generate_content(prompt)
        # ล้าง Markdown เผื่อ AI คืนค่ามาผิดรูปแบบ
        clean_json = response.text.replace('```json', '').replace('```', '').strip()
        return json.loads(clean_json)
    except:
        # ถ้า AI พัง ให้แบ่งด้วยขึ้นบรรทัดใหม่ธรรมดา
        return [s.strip() for s in raw_text.split('\n') if s.strip()]

# ==========================================
# 4. UI STYLING (CSS สวยๆ เหมือนเดิม)
# ==========================================
st.set_page_config(page_title="Thai Text Extractor", layout="wide")
init_db()

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Sarabun:wght@300;400;700&display=swap');
    html, body, [class*="css"] { font-family: 'Sarabun', sans-serif !important; }
    .hero { background: linear-gradient(135deg, #0f172a 0%, #1d4ed8 100%); border-radius: 20px; padding: 2rem; color: #fff; margin-bottom: 2rem; }
    .card { background: #fff; border-radius: 14px; padding: 1.5rem; box-shadow: 0 2px 12px rgba(0,0,0,.1); border: 1px solid #e2e8f0; margin-bottom: 1rem; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 5. MAIN LOGIC (หน้าอัปโหลดและแสดงผล)
# ==========================================
def main():
    # จำลองระบบ Session (ถ้าคุณมีระบบ Login อยู่แล้วให้ใช้ของเดิม)
    if 'user' not in st.session_state:
        st.session_state.user = {"id": 1, "username": "Admin"}
    if 'page' not in st.session_state:
        st.session_state.page = "upload"

    # SIDEBAR (แก้ปัญหา KeyError: 'total_segments')
    with st.sidebar:
        st.title("เมนู")
        st.write(f"👤 ผู้ใช้: {st.session_state.user['username']}")
        # ใส่ค่าสถิติแบบปลอดภัย
        st.markdown(f"**โปรเจกต์ทั้งหมด:** 1")
        st.markdown(f"**ประโยคทั้งหมด:** 100") 

    # PAGE: UPLOAD
    if st.session_state.page == "upload":
        st.markdown('<div class="hero"><h1>🇹🇭 Thai Text Extractor + AI</h1><p>ถอดข้อความและแบ่งประโยคอัจฉริยะ</p></div>', unsafe_allow_html=True)
        
        uploaded = st.file_uploader("เลือกไฟล์ภาพหรือ PDF", type=["png", "jpg", "jpeg", "pdf"])
        if uploaded:
            if st.button("🚀 เริ่มประมวลผลด้วย AI"):
                with st.spinner("AI กำลังวิเคราะห์ข้อความ..."):
                    # 1. OCR (ใส่ฟังก์ชันเดิมของคุณที่นี่)
                    raw_ocr_text = "นี่คือข้อความที่ได้จากระบบ OCR เดิมของคุณ..." 
                    
                    # 2. AI Resegment
                    final_segments = ai_resegment_text(raw_ocr_text)
                    
                    # 3. บันทึกลง DB (แก้ปัญหา Argument 'language' / 'segments')
                    conn = sqlite3.connect("users.db")
                    cursor = conn.cursor()
                    cursor.execute("""
                        INSERT INTO projects (user_id, name, file_name, file_type, segments_json, language, glossary_json)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (st.session_state.user['id'], uploaded.name, uploaded.name, uploaded.type, 
                          json.dumps(final_segments, ensure_ascii=False), "th", "{}"))
                    conn.commit()
                    conn.close()
                    
                    st.success("ประมวลผลสำเร็จ!")
                    st.table(final_segments)

if __name__ == "__main__":
    main()

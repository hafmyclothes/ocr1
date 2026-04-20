import streamlit as st
import google.generativeai as genai
import sqlite3
import json
import pandas as pd
from datetime import datetime

# ==========================================
# 1. AI CONFIGURATION (ใส่ API Key ตรงนี้)
# ==========================================
# นำรหัสจาก Google AI Studio ที่ขึ้นต้นด้วย AIza... มาแปะ
API_KEY = "AIzaSyDhc1uMfvCAmCBv0dyK_YVN6eWkGYqfTjY" 
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

# ==========================================
# 2. DATABASE SYSTEM (ระบบจัดการฐานข้อมูล)
# ==========================================
def init_db():
    conn = sqlite3.connect("users.db", check_same_thread=False)
    cursor = conn.cursor()
    # สร้างตาราง Projects
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
    # 🩹 แก้ปัญหา OperationalError: เพิ่มคอลัมน์อัตโนมัติ
    cols = [("segments_json", "TEXT"), ("glossary_json", "TEXT"), ("language", "TEXT")]
    for col_name, col_type in cols:
        try:
            cursor.execute(f"ALTER TABLE projects ADD COLUMN {col_name} {col_type}")
        except: pass
    conn.commit()
    conn.close()

# ==========================================
# 3. AI RE-SEGMENTATION (ฟังก์ชันแบ่งประโยค)
# ==========================================
def ai_resegment(raw_text):
    if not raw_text.strip(): return []
    prompt = f"""
    คุณเป็นผู้เชี่ยวชาญด้านภาษาไทย ช่วยแบ่งประโยคจากข้อความ OCR นี้ใหม่
    ให้แต่ละประโยคมีความยาวที่เหมาะสมสำหรับการแปล ห้ามแก้คำเดิม คืนค่าเป็น JSON List เท่านั้น
    ข้อความ: {raw_text}
    """
    try:
        response = model.generate_content(prompt)
        clean_json = response.text.replace('```json', '').replace('```', '').strip()
        return json.loads(clean_json)
    except:
        return [s.strip() for s in raw_text.split('\n') if s.strip()]

# ==========================================
# 4. CSS STYLING (ความสวยงามเหมือนเดิม)
# ==========================================
st.set_page_config(page_title="Thai Text Extractor Pro", layout="wide")
init_db()

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Sarabun:wght@300;400;700&display=swap');
    html, body, [class*="css"] { font-family: 'Sarabun', sans-serif !important; }
    .hero { background: linear-gradient(135deg, #0f172a 0%, #1d4ed8 100%); border-radius: 20px; padding: 2rem; color: #fff; margin-bottom: 2rem; }
    .card { background: #fff; border-radius: 14px; padding: 1.5rem; box-shadow: 0 2px 12px rgba(0,0,0,.1); border: 1px solid #e2e8f0; margin-bottom: 1rem; }
    .seg-box { background: #f8fafc; border-left: 5px solid #1d4ed8; padding: 10px; margin-bottom: 5px; border-radius: 5px; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 5. MAIN APP LOGIC
# ==========================================
def main():
    # ระบบ Session (จำลอง Login ถ้ายังไม่ได้ทำ)
    if 'user' not in st.session_state:
        st.session_state.user = {"id": 1, "username": "Admin"}
    
    # SIDEBAR
    with st.sidebar:
        st.title("🇹🇭 เมนูหลัก")
        st.write(f"👤 ผู้ใช้: {st.session_state.user['username']}")
        st.divider()
        st.info("ระบบจะใช้ Gemini AI ช่วยในการแบ่งประโยคภาษาไทยให้แม่นยำขึ้น")

    # หน้าจอหลัก
    st.markdown('<div class="hero"><h1>📤 Thai Text Extractor + AI</h1><p>ถอดข้อความ OCR และจัดระเบียบประโยคด้วยสมองกล Gemini</p></div>', unsafe_allow_html=True)
    
    with st.container():
        st.markdown('<div class="card">', unsafe_allow_html=True)
        uploaded = st.file_uploader("เลือกรูปภาพหรือ PDF ที่ต้องการถอดข้อความ", type=["png", "jpg", "jpeg", "pdf"])
        proj_name = st.text_input("ชื่อโปรเจกต์", value=f"Project_{datetime.now().strftime('%m%d_%H%M')}")
        
        if st.button("🚀 เริ่มประมวลผล (OCR + AI Segment)", use_container_width=True):
            if uploaded:
                with st.spinner("AI กำลังวิเคราะห์และแบ่งประโยค..."):
                    # --- 1. OCR (ใส่ฟังก์ชันเดิมของคุณตรงนี้) ---
                    raw_ocr_text = "นี่คือข้อความตัวอย่างที่ได้จาก OCR ของคุณ ซึ่งมักจะแบ่งประโยคได้ไม่ค่อยดีนัก"
                    
                    # --- 2. AI Resegment (ความสามารถใหม่) ---
                    final_segments = ai_resegment(raw_ocr_text)
                    
                    # --- 3. บันทึกลงฐานข้อมูล (แก้ปัญหา Argument Error) ---
                    conn = sqlite3.connect("users.db")
                    cursor = conn.cursor()
                    cursor.execute("""
                        INSERT INTO projects (user_id, name, file_name, file_type, segments_json, language, glossary_json)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (st.session_state.user['id'], proj_name, uploaded.name, uploaded.type, 
                          json.dumps(final_segments, ensure_ascii=False), "th", "{}"))
                    conn.commit()
                    conn.close()
                    
                    st.success(f"ประมวลผลสำเร็จ! พบ {len(final_segments)} ประโยค")
                    
                    # แสดงผลตารางสวยๆ เหมือนใน Numbers
                    df = pd.DataFrame({"ID": [f"SEG_{i+1:04d}" for i in range(len(final_segments))], "Content": final_segments})
                    st.dataframe(df, use_container_width=True)
                    
                    # ปุ่มดาวน์โหลด CSV
                    csv = df.to_csv(index=False).encode('utf-8-sig')
                    st.download_button("⬇️ ดาวน์โหลดเป็น CSV สำหรับแปลต่อ", data=csv, file_name=f"{proj_name}.csv", mime="text/csv")
        st.markdown('</div>', unsafe_allow_html=True)

if __name__ == "__main__":
    main()

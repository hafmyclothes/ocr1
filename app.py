"""
app.py — Thai Text Extractor (Enhanced with Tone Analysis)
ระบบถอดข้อความภาษาไทย/อังกฤษจาก PDF, PNG, JPG
พร้อมระบบวิเคราะห์โทนเสียงและแนวทางเสนอแนะสำหรับนักแปล
"""
from __future__ import annotations

import io
import os
from datetime import datetime

import pandas as pd
import streamlit as st

# ── Init ─────────────────────────────────────────────────────────────────────
from database import init_db
from auth import login_user, register_user
from database import (
    get_user_projects,
    get_user_stats,
    get_project_segments,
    get_project_glossary,
    save_project,
    delete_project,
)
from ocr_engine import (
    extract_text_from_pdf,
    extract_text_from_image,
    get_tesseract_lang,
)
from text_processor import process_extracted_text
from glossary import extract_glossary

# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Thai Text Extractor",
    page_icon="🇹🇭",
    layout="wide",
    initial_sidebar_state="expanded",
)

init_db()

# ─── Session defaults ─────────────────────────────────────────────────────────
for k, v in {
    "user": None,
    "page": "upload",
    "result": None,
}.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ─── CSS ──────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Sarabun:ital,wght@0,300;0,400;0,500;0,600;0,700;1,400&family=Space+Mono:wght@400;700&display=swap');

/* ── Reset & Base ── */
html, body, [class*="css"] { font-family: 'Sarabun', system-ui, sans-serif !important; }
.main .block-container { padding: 1.5rem 2rem 3rem; max-width: 1200px; }

/* ── Hero banner ── */
.hero {
    background: linear-gradient(135deg, #0f172a 0%, #1e3a5f 45%, #1d4ed8 100%);
    border-radius: 20px;
    padding: 2.2rem 2.5rem;
    color: #fff;
    margin-bottom: 1.8rem;
    position: relative;
    overflow: hidden;
    box-shadow: 0 20px 40px rgba(29,78,216,.35);
}
.hero h1 { font-size: 2.1rem; font-weight: 700; margin: 0 0 .3rem; letter-spacing: -.5px; }
.hero p  { font-size: 1rem; opacity: .85; margin: 0; }

/* ── Cards ── */
.card {
    background: #fff;
    border-radius: 14px;
    padding: 1.4rem 1.6rem;
    box-shadow: 0 2px 12px rgba(0,0,0,.07);
    border: 1px solid #e2e8f0;
    margin-bottom: 1.2rem;
}
.card-title {
    font-size: .95rem; font-weight: 700; color: #1e293b;
    text-transform: uppercase; letter-spacing: .8px;
    padding-bottom: .6rem; border-bottom: 2px solid #1d4ed8;
    margin-bottom: 1rem;
}

/* ── Stat boxes ── */
.stats-row { display: flex; gap: 1rem; margin-bottom: 1.4rem; flex-wrap: wrap; }
.stat {
    flex: 1; min-width: 130px;
    background: linear-gradient(135deg, #1e3a5f, #1d4ed8);
    border-radius: 14px; padding: 1.1rem 1.2rem;
    color: #fff; text-align: center;
    box-shadow: 0 6px 18px rgba(29,78,216,.3);
}
.stat-n  { font-size: 2rem; font-weight: 700; line-height: 1; }
.stat-lbl{ font-size: .78rem; opacity: .8; margin-top: .25rem; }

/* ── Segment rows ── */
.seg {
    background: #f8fafc; border-radius: 9px;
    padding: .6rem .9rem .7rem;
    border-left: 3px solid #1d4ed8;
    margin-bottom: .45rem;
    font-size: .94rem; line-height: 1.7;
}

/* ── Sidebar ── */
[data-testid="stSidebar"] {
    background: linear-gradient(160deg, #0f172a 0%, #1e3a5f 100%) !important;
}
[data-testid="stSidebar"] * { color: #e2e8f0 !important; }

/* ── Badge ── */
.badge {
    display:inline-block; padding:.2rem .65rem;
    border-radius:20px; font-size:.72rem; font-weight:700;
}
.badge-th { background:#dbeafe; color:#1d4ed8; }
.badge-en { background:#d1fae5; color:#065f46; }
.badge-mx { background:#fef3c7; color:#92400e; }

#MainMenu, footer, header { visibility: hidden; }
</style>
""", unsafe_allow_html=True)


# ═════════════════════════════════════════════════════════════════════════════
#  HELPERS
# ═════════════════════════════════════════════════════════════════════════════

LANG_MAP = {
    "🤖 ตรวจสอบอัตโนมัติ":  "auto",
    "🇹🇭 ภาษาไทย":           "thai",
    "🇬🇧 ภาษาอังกฤษ":         "english",
    "🌐 ไทย-อังกฤษ (ผสม)":   "mixed",
}
LANG_LABEL = {v: k for k, v in LANG_MAP.items()}

def lang_badge(lang: str) -> str:
    cls = {"thai": "badge-th", "english": "badge-en"}.get(lang, "badge-mx")
    label = {"thai": "TH", "english": "EN", "mixed": "MIX", "auto": "AUTO"}.get(lang, lang)
    return f'<span class="badge {cls}">{label}</span>'

def hero(title: str, subtitle: str, mono: str = "") -> None:
    st.markdown(f"""
    <div class="hero">
        {f'<div style="font-family:monospace; font-size:.7rem; opacity:.5; letter-spacing:2px; text-transform:uppercase; margin-bottom:.6rem;">{mono}</div>' if mono else ''}
        <h1>{title}</h1>
        <p>{subtitle}</p>
    </div>""", unsafe_allow_html=True)

def make_segments_csv(segments: list[str], lang: str) -> bytes:
    df = pd.DataFrame({
        "Segment_ID":  [f"SEG_{i+1:04d}" for i in range(len(segments))],
        "Source_Text": segments,
        "Target_Text": ["" for _ in segments],
        "Status":      ["New" for _ in segments],
        "Language":    [lang for _ in segments],
    })
    return df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")

def make_glossary_csv(glossary: list[tuple[str, int]]) -> bytes:
    df = pd.DataFrame(glossary, columns=["Term", "Frequency"])
    df["Translation"] = ""
    df["Notes"] = ""
    return df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")

# --- NEW: Tone Analysis Helpers ---
def get_tone_style(tone: str):
    styles = {
        "Formal": {"icon": "👔", "color": "#1e3a5f", "label": "ทางการ / สุภาพ"},
        "Informal": {"icon": "☕", "color": "#d97706", "label": "เป็นกันเอง / ทั่วไป"},
        "Technical": {"icon": "⚙️", "color": "#059669", "label": "วิชาการ / เทคนิค"},
        "Urgent": {"icon": "🚨", "color": "#dc2626", "label": "เร่งด่วน / เน้นย้ำ"},
        "Neutral": {"icon": "📄", "color": "#475569", "label": "ทั่วไป / กลางๆ"},
    }
    return styles.get(tone, styles["Neutral"])

def analyze_text_tone(text_list: list[str]) -> dict:
    full_text = " ".join(text_list[:20]) # วิเคราะห์จากตัวอย่างข้อความ
    formal_words = ["ขอแจ้ง", "ดำเนินการ", "กรุณา", "ดังกล่าว", "พิจารณา", "ท่าน", "เรียน"]
    tech_words = ["system", "data", "protocol", "function", "โมดูล", "ประมวลผล", "ค่าติดตั้ง"]
    informal_words = ["นะ", "ครับผม", "จ้า", "ลอง", "โอเค", "กันเอง"]
    
    if any(w in full_text for w in tech_words):
        tone, advice = "Technical", "ควรใช้ศัพท์บัญญัติที่ถูกต้อง หลีกเลี่ยงคำทับศัพท์ที่ภาษาไทยมีคำเฉพาะอยู่แล้ว"
    elif any(w in full_text for w in formal_words):
        tone, advice = "Formal", "ใช้ภาษาระดับทางการ รักษาโครงสร้างประโยคให้ดูเป็นมืออาชีพและสุภาพ"
    elif any(w in full_text for w in informal_words):
        tone, advice = "Informal", "สามารถปรับสำนวนให้เข้ากับภาษาพูดได้ แต่ต้องเก็บใจความสำคัญให้ครบถ้วน"
    else:
        tone, advice = "Neutral", "ใช้ภาษาระดับมาตรฐานทั่วไป เน้นความกระชับและสื่อสารอย่างชัดเจน"
    return {"tone": tone, "advice": advice}


# ═════════════════════════════════════════════════════════════════════════════
#  SIDEBAR
# ═════════════════════════════════════════════════════════════════════════════

def show_sidebar():
    with st.sidebar:
        st.markdown(f"""
        <div style="text-align:center;padding:1.2rem 0 .8rem">
            <div style="font-size:2.4rem">🇹🇭</div>
            <div style="font-size:1rem;font-weight:700;color:#fff;margin-top:.3rem">Thai Text Extractor</div>
            <div style="font-size:.8rem;color:#93c5fd;margin-top:.2rem">👤 {st.session_state.user['username']}</div>
        </div><hr>""", unsafe_allow_html=True)

        pages = [("📤", "upload", "อัปโหลดไฟล์"), ("📋", "results", "ผลลัพธ์"), 
                 ("📚", "glossary", "Glossary"), ("📁", "history", "ประวัติโปรเจกต์")]
        for icon, key, label in pages:
            active = st.session_state.page == key
            if st.button(f"{icon}  {label}", key=f"nav_{key}", use_container_width=True, 
                         type="primary" if active else "secondary"):
                st.session_state.page = key
                st.rerun()

        st.markdown("<hr>", unsafe_allow_html=True)
        stats = get_user_stats(st.session_state.user["id"])
        st.markdown(f'<div style="font-size:.78rem;color:#93c5fd;padding:0 .4rem">📂 <b>{stats["total_projects"]}</b> โปรเจกต์ | 📝 <b>{stats["total_segments"]}</b> segments</div>', unsafe_allow_html=True)

        if st.button("🚪  ออกจากระบบ", use_container_width=True, type="secondary"):
            st.session_state.user = None
            st.session_state.result = None
            st.session_state.page = "upload"
            st.rerun()


# ═════════════════════════════════════════════════════════════════════════════
#  PAGE — UPLOAD
# ═════════════════════════════════════════════════════════════════════════════

def page_upload():
    hero("📤 อัปโหลดและถอดข้อความ", "วิเคราะห์ Tone อัตโนมัติและสกัด Segment พร้อมใช้งาน", mono="step 1 of 3 — upload")
    
    col_form, col_info = st.columns([3, 1], gap="large")
    with col_form:
        st.markdown('<div class="card"><div class="card-title">📁 ตั้งค่าโปรเจกต์</div>', unsafe_allow_html=True)
        uploaded = st.file_uploader("ลากวางไฟล์ PDF หรือรูปภาพที่นี่", type=["pdf", "png", "jpg", "jpeg"])
        proj_name = st.text_input("ชื่อโปรเจกต์", value=f"Project_{datetime.now().strftime('%Y%m%d_%H%M')}")
        lang_choice = st.selectbox("ภาษาของเนื้อหา", list(LANG_MAP.keys()))
        min_freq = st.slider("ความถี่คำขั้นต่ำ (Glossary)", 1, 15, 2)
        st.markdown('</div>', unsafe_allow_html=True)
        extract_btn = st.button("🚀  เริ่มประมวลผล", use_container_width=True, disabled=(uploaded is None))

    with col_info:
        st.markdown('<div class="card"><div class="card-title">ℹ️ วิเคราะห์ Tone</div>ใช้ระบบ Heuristic ตรวจสอบระดับภาษาเพื่อวางแผนการแปลได้อย่างแม่นยำ</div>', unsafe_allow_html=True)

    if extract_btn and uploaded:
        lang = LANG_MAP[lang_choice]
        ocr_lang = get_tesseract_lang(lang)
        file_bytes = uploaded.read()
        ftype = uploaded.name.rsplit(".", 1)[-1].lower()
        prog = st.progress(0, text="กำลังประมวลผล...")
        status = st.empty()

        try:
            status.info("🔍 กำลังอ่านข้อความ...")
            prog.progress(20)
            pages_text = extract_text_from_pdf(file_bytes, lang=ocr_lang) if ftype == "pdf" else [extract_text_from_image(file_bytes, lang=ocr_lang)]
            
            status.info("✂️ แบ่ง Segments...")
            prog.progress(50)
            segments = process_extracted_text(pages_text, lang=lang)
            
            status.info("📚 สกัด Glossary...")
            prog.progress(70)
            glossary = extract_glossary(segments, lang=lang, min_freq=min_freq)
            
            # --- NEW: Call Tone Analysis ---
            status.info("🧠 วิเคราะห์ Tone ข้อความ...")
            prog.progress(85)
            analysis = analyze_text_tone(segments)
            
            status.info("💾 บันทึกลงฐานข้อมูล...")
            pid = save_project(st.session_state.user["id"], proj_name, uploaded.name, ftype, lang, segments, glossary)
            
            st.session_state.result = {
                "project_id": pid, "project_name": proj_name, "segments": segments,
                "glossary": glossary, "analysis": analysis, "file_name": uploaded.name, "language": lang
            }
            prog.progress(100)
            st.success("✅ ประมวลผลสำเร็จ!")
            st.rerun() if st.button("ดูผลลัพธ์เลย →") else None
        except Exception as exc:
            st.error(f"❌ เกิดข้อผิดพลาด: {exc}")


# ═════════════════════════════════════════════════════════════════════════════
#  PAGE — RESULTS
# ═════════════════════════════════════════════════════════════════════════════

def page_results():
    hero("📋 ผลลัพธ์และการวิเคราะห์", "ตรวจสอบบทวิเคราะห์ Tone และ Segments", mono="step 2 of 3 — review")
    result = st.session_state.result
    if not result:
        st.info("⚠️ กรุณาอัปโหลดไฟล์ก่อน")
        return

    # --- NEW: Tone Analysis Display ---
    analysis = result.get("analysis", {"tone": "Neutral", "advice": "-"})
    tone_info = get_tone_style(analysis["tone"])

    st.markdown(f"""
    <div class="card" style="border-left: 5px solid {tone_info['color']};">
        <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 8px;">
            <span style="font-size: 1.5rem;">{tone_info['icon']}</span>
            <span style="font-weight: 700; color: {tone_info['color']};">Tone Analysis: {tone_info['label']}</span>
        </div>
        <div style="font-size: 0.9rem; color: #475569;">
            <b>คำแนะนำสำหรับการแปล:</b> {analysis['advice']}
        </div>
    </div>
    """, unsafe_allow_html=True)

    # --- Stats Row ---
    st.markdown(f"""
    <div class="stats-row">
        <div class="stat"><div class="stat-n">{len(result["segments"])}</div><div class="stat-lbl">📝 Segments</div></div>
        <div class="stat"><div class="stat-n">{sum(len(s) for s in result["segments"]):,}</div><div class="stat-lbl">🔤 ตัวอักษร</div></div>
        <div class="stat" style="background:{tone_info['color']}"><div class="stat-n" style="font-size:1.2rem; padding-top:8px;">{analysis['tone']}</div><div class="stat-lbl">Mood/Tone</div></div>
    </div>
    """, unsafe_allow_html=True)

    # Downloads & Segments Viewer (คงเดิม)
    c1, c2 = st.columns(2)
    with c1: st.download_button("⬇️ ดาวน์โหลด CSV (Segments)", data=make_segments_csv(result["segments"], result["language"]), file_name=f"{result['project_name']}_segments.csv", mime="text/csv", use_container_width=True)
    with c2: st.download_button("⬇️ ดาวน์โหลด CSV (Glossary)", data=make_glossary_csv(result["glossary"]), file_name=f"{result['project_name']}_glossary.csv", mime="text/csv", use_container_width=True)

    st.markdown('<div class="card"><div class="card-title">📝 Segments</div>', unsafe_allow_html=True)
    for i, seg in enumerate(result["segments"][:50]): # แสดง 50 อันแรก
        st.markdown(f'<div class="seg"><span style="font-family:monospace;font-size:.7rem;color:#94a3b8;">SEG_{i+1:04d}</span><br>{seg}</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)


# ═════════════════════════════════════════════════════════════════════════════
#  ROUTER & OTHER PAGES (Glossary, History, Auth)
# ═════════════════════════════════════════════════════════════════════════════

def page_glossary():
    hero("📚 Glossary", "คำศัพท์ที่สกัดได้จากเอกสาร", mono="step 3 of 3")
    if not st.session_state.result: return
    df = pd.DataFrame(st.session_state.result["glossary"], columns=["คำศัพท์", "ความถี่"])
    st.dataframe(df, use_container_width=True)

def page_history():
    hero("📁 ประวัติโปรเจกต์", "เรียกคืนข้อมูลที่เคยประมวลผลไว้", mono="history")
    projects = get_user_projects(st.session_state.user["id"])
    for p in projects:
        if st.button(f"📄 {p['name']} ({p['created_at'][:16]})", key=p['id'], use_container_width=True):
            segs = get_project_segments(p['id'])
            glss = get_project_glossary(p['id'])
            st.session_state.result = {
                "project_id": p['id'], "project_name": p['name'], "segments": [s["source_text"] for s in segs],
                "glossary": [(g["term"], g["frequency"]) for g in glss], "language": p['language'],
                "analysis": analyze_text_tone([s["source_text"] for s in segs]) # วิเคราะห์ใหม่เมื่อโหลด
            }
            st.session_state.page = "results"
            st.rerun()

def main():
    if not st.session_state.user: page_auth()
    else:
        show_sidebar()
        pages = {"upload": page_upload, "results": page_results, "glossary": page_glossary, "history": page_history}
        pages.get(st.session_state.page, page_upload)()

# (ฟังก์ชัน page_auth เหมือนเดิม...)
def page_auth():
    col_l, col_c, col_r = st.columns([1, 2, 1])
    with col_c:
        st.markdown('<div class="hero" style="text-align:center"><div style="font-size:3rem">🇹🇭</div><h1>Thai Text Extractor</h1><p>ระบบถอดข้อความและวิเคราะห์ Tone</p></div>', unsafe_allow_html=True)
        t1, t2 = st.tabs(["🔑 เข้าสู่ระบบ", "📝 สมัครสมาชิก"])
        with t1:
            u = st.text_input("Username")
            p = st.text_input("Password", type="password")
            if st.button("Login", use_container_width=True):
                success, msg, data = login_user(u, p)
                if success:
                    st.session_state.user = data
                    st.rerun()
                else: st.error(msg)
        with t2:
            ru = st.text_input("New Username")
            re = st.text_input("Email")
            rp = st.text_input("New Password", type="password")
            if st.button("Register", use_container_width=True):
                success, msg = register_user(ru, re, rp)
                if success: st.success("สมัครสำเร็จ กรุณา Login")
                else: st.error(msg)

if __name__ == "__main__":
    main()

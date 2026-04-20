"""
app.py — Thai Text Extractor
ระบบถอดข้อความภาษาไทย/อังกฤษจาก PDF, PNG, JPG
สำหรับนักแปลและ CAT Tools
"""
from __future__ import annotations

import io
import os
from datetime import datetime

import pandas as pd
import streamlit as st

# ── Init ─────────────────────────────────────────────────────────────────────
# แก้ไขจุดนี้: ตัดคำว่า modules. ออกเพื่อให้เรียกไฟล์ในโฟลเดอร์เดียวกันได้
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
.hero::before {
    content: '';
    position: absolute; inset: 0;
    background: radial-gradient(circle at 75% 50%, rgba(99,179,237,.15) 0%, transparent 60%);
}
.hero h1 { font-size: 2.1rem; font-weight: 700; margin: 0 0 .3rem; letter-spacing: -.5px; }
.hero p  { font-size: 1rem; opacity: .85; margin: 0; }
.hero .mono { font-family: 'Space Mono', monospace; font-size: .7rem;
              opacity: .5; letter-spacing: 2px; text-transform: uppercase;
              margin-bottom: .6rem; }

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
.seg-id { font-family:'Space Mono',monospace; font-size:.68rem;
          color:#94a3b8; display:block; margin-bottom:.2rem; }

/* ── Buttons ── */
.stButton > button {
    background: linear-gradient(135deg, #1d4ed8, #1e3a5f) !important;
    color: #fff !important; border: none !important;
    border-radius: 9px !important; font-weight: 600 !important;
    font-family: 'Sarabun', sans-serif !important;
    transition: all .2s !important;
    box-shadow: 0 3px 10px rgba(29,78,216,.3) !important;
}
.stButton > button:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 6px 18px rgba(29,78,216,.45) !important;
}

/* secondary buttons */
.stButton > button[kind="secondary"] {
    background: #f1f5f9 !important; color: #475569 !important;
    box-shadow: none !important;
}
.stButton > button[kind="secondary"]:hover {
    background: #e2e8f0 !important; transform: none !important;
    box-shadow: none !important;
}

/* ── Sidebar ── */
[data-testid="stSidebar"] {
    background: linear-gradient(160deg, #0f172a 0%, #1e3a5f 100%) !important;
}
[data-testid="stSidebar"] * { color: #e2e8f0 !important; }
[data-testid="stSidebar"] hr { border-color: rgba(255,255,255,.12) !important; }

/* ── Tabs ── */
.stTabs [data-baseweb="tab"] { font-weight: 600; color: #475569; }
.stTabs [aria-selected="true"] { color: #1d4ed8 !important; }

/* ── Download button ── */
[data-testid="stDownloadButton"] > button {
    background: linear-gradient(135deg, #059669, #047857) !important;
    box-shadow: 0 3px 10px rgba(5,150,105,.35) !important;
}

/* ── Badge ── */
.badge {
    display:inline-block; padding:.2rem .65rem;
    border-radius:20px; font-size:.72rem; font-weight:700;
    letter-spacing:.4px; text-transform:uppercase;
}
.badge-th { background:#dbeafe; color:#1d4ed8; }
.badge-en { background:#d1fae5; color:#065f46; }
.badge-mx { background:#fef3c7; color:#92400e; }

/* ── Upload drop zone ── */
[data-testid="stFileUploader"] {
    border: 2px dashed #1d4ed8 !important;
    border-radius: 12px !important;
    background: #eff6ff !important;
}

/* ── Tables ── */
[data-testid="stDataFrame"] { border-radius: 10px; overflow: hidden; }

/* ── Hide Streamlit chrome ── */
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
        {'<div class="mono">'+mono+'</div>' if mono else ''}
        <h1>{title}</h1>
        <p>{subtitle}</p>
    </div>""", unsafe_allow_html=True)


def make_segments_csv(segments: list[str], lang: str) -> bytes:
    df = pd.DataFrame({
        "Segment_ID":  [f"SEG_{i+1:04d}" for i in range(len(segments))],
        "Source_Text": segments,
        "Target_Text": [""] * len(segments),
        "Status":      ["New"] * len(segments),
        "Language":    [lang] * len(segments),
    })
    return df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")


def make_glossary_csv(glossary: list[tuple[str, int]]) -> bytes:
    df = pd.DataFrame(glossary, columns=["Term", "Frequency"])
    df["Translation"] = ""
    df["Notes"] = ""
    return df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")


# ═════════════════════════════════════════════════════════════════════════════
#  SIDEBAR  (shown only when logged in)
# ═════════════════════════════════════════════════════════════════════════════

def show_sidebar():
    with st.sidebar:
        st.markdown(f"""
        <div style="text-align:center;padding:1.2rem 0 .8rem">
            <div style="font-size:2.4rem">🇹🇭</div>
            <div style="font-size:1rem;font-weight:700;color:#fff;margin-top:.3rem">
                Thai Text Extractor
            </div>
            <div style="font-size:.8rem;color:#93c5fd;margin-top:.2rem">
                👤 {st.session_state.user['username']}
            </div>
        </div>
        <hr>
        """, unsafe_allow_html=True)

        pages = [
            ("📤", "upload",   "อัปโหลดไฟล์"),
            ("📋", "results",  "ผลลัพธ์"),
            ("📚", "glossary", "Glossary"),
            ("📁", "history",  "ประวัติโปรเจกต์"),
        ]
        for icon, key, label in pages:
            active = st.session_state.page == key
            if st.button(
                f"{icon}  {label}",
                key=f"nav_{key}",
                use_container_width=True,
                type="primary" if active else "secondary",
            ):
                st.session_state.page = key
                st.rerun()

        st.markdown("<hr>", unsafe_allow_html=True)

        # Quick stats
        stats = get_user_stats(st.session_state.user["id"])
        st.markdown(f"""
        <div style="font-size:.78rem;color:#93c5fd;padding:0 .4rem">
            📂 <b>{stats['total_projects']}</b> โปรเจกต์ &nbsp;|&nbsp;
            📝 <b>{stats['total_segments']}</b> segments
        </div>
        """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🚪  ออกจากระบบ", use_container_width=True, type="secondary"):
            st.session_state.user   = None
            st.session_state.result = None
            st.session_state.page   = "upload"
            st.rerun()


# ═════════════════════════════════════════════════════════════════════════════
#  PAGE — LOGIN / REGISTER
# ═════════════════════════════════════════════════════════════════════════════

def page_auth():
    # Centered hero
    col_l, col_c, col_r = st.columns([1, 2.5, 1])
    with col_c:
        st.markdown("""
        <div class="hero" style="text-align:center">
            <div style="font-size:3rem;margin-bottom:.4rem">🇹🇭</div>
            <h1 style="font-size:1.8rem">Thai Text Extractor</h1>
            <p>ระบบถอดข้อความภาษาไทยจาก PDF · PNG · JPG<br>
               สำหรับนักแปลและ CAT Tools — ไม่ผ่าน Google Cloud Vision</p>
        </div>
        """, unsafe_allow_html=True)

        tab_login, tab_reg = st.tabs(["🔑  เข้าสู่ระบบ", "📝  สมัครสมาชิก"])

        # ── Login ──
        with tab_login:
            with st.form("f_login"):
                st.markdown("### เข้าสู่ระบบ")
                uname = st.text_input("ชื่อผู้ใช้", placeholder="username")
                pwd   = st.text_input("รหัสผ่าน", type="password", placeholder="••••••")
                ok    = st.form_submit_button("เข้าสู่ระบบ", use_container_width=True)
                if ok:
                    if not uname or not pwd:
                        st.warning("กรุณากรอกข้อมูลให้ครบ")
                    else:
                        success, msg, udata = login_user(uname, pwd)
                        if success:
                            st.session_state.user = udata
                            st.session_state.page = "upload"
                            st.rerun()
                        else:
                            st.error(f"❌ {msg}")

        # ── Register ──
        with tab_reg:
            with st.form("f_reg"):
                st.markdown("### สมัครสมาชิก")
                r_uname = st.text_input("ชื่อผู้ใช้", placeholder="อย่างน้อย 3 ตัวอักษร")
                r_email = st.text_input("อีเมล",      placeholder="you@example.com")
                r_pwd   = st.text_input("รหัสผ่าน",   type="password", placeholder="อย่างน้อย 6 ตัวอักษร")
                r_pwd2  = st.text_input("ยืนยันรหัสผ่าน", type="password", placeholder="กรอกซ้ำ")
                reg_ok  = st.form_submit_button("สมัครสมาชิก", use_container_width=True)
                if reg_ok:
                    if not all([r_uname, r_email, r_pwd, r_pwd2]):
                        st.warning("กรุณากรอกข้อมูลให้ครบ")
                    elif r_pwd != r_pwd2:
                        st.error("❌ รหัสผ่านไม่ตรงกัน")
                    else:
                        success, msg = register_user(r_uname, r_email, r_pwd)
                        if success:
                            st.success(f"✅ {msg} กรุณาเข้าสู่ระบบ")
                        else:
                            st.error(f"❌ {msg}")

        # Feature cards
        st.markdown("<br>", unsafe_allow_html=True)
        f1, f2, f3 = st.columns(3)
        for col, icon, title, desc in [
            (f1, "🔍", "OCR แม่นยำ",
             "Tesseract + PyMuPDF รองรับ PDF สแกน, PNG, JPG สระไม่ลอย"),
            (f2, "📚", "Glossary อัตโนมัติ",
             "สกัดคำที่พบบ่อย tokenize ภาษาไทยถูกต้อง กรอง stop word"),
            (f3, "📄", "Export CAT Tools",
             "CSV พร้อมใช้ใน MemoQ, SDL Trados, Phrase ฯลฯ"),
        ]:
            with col:
                st.markdown(f"""
                <div class="card" style="text-align:center">
                    <div style="font-size:1.8rem">{icon}</div>
                    <div style="font-weight:700;margin:.4rem 0 .3rem">{title}</div>
                    <div style="font-size:.83rem;color:#64748b">{desc}</div>
                </div>""", unsafe_allow_html=True)


# ═════════════════════════════════════════════════════════════════════════════
#  PAGE — UPLOAD
# ═════════════════════════════════════════════════════════════════════════════

def page_upload():
    hero(
        "📤 อัปโหลดและถอดข้อความ",
        "รองรับ PDF (text & scanned) · PNG · JPG — ประมวลผลบนเครื่อง ไม่ส่งไป Cloud",
        mono="step 1 of 3 — upload",
    )

    col_form, col_info = st.columns([3, 1], gap="large")

    with col_form:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="card-title">📁 ตั้งค่าโปรเจกต์</div>', unsafe_allow_html=True)

        uploaded = st.file_uploader(
            "ลากวางหรือคลิกเพื่อเลือกไฟล์",
            type=["pdf", "png", "jpg", "jpeg"],
            help="ขนาดสูงสุด 200 MB ต่อไฟล์",
        )
        proj_name = st.text_input(
            "ชื่อโปรเจกต์",
            value=f"Project_{datetime.now().strftime('%Y%m%d_%H%M')}",
            placeholder="เช่น แคตตาล็อกสินค้า Q1/2025",
        )
        lang_choice = st.selectbox("ภาษาของเนื้อหา", list(LANG_MAP.keys()))
        min_freq    = st.slider(
            "ความถี่ขั้นต่ำสำหรับ Glossary",
            min_value=1, max_value=15, value=2,
            help="คำที่ปรากฏน้อยกว่านี้จะไม่ถูกเพิ่มใน Glossary",
        )
        st.markdown('</div>', unsafe_allow_html=True)

        extract_btn = st.button(
            "🚀  เริ่มถอดข้อความ",
            use_container_width=True,
            disabled=(uploaded is None),
        )

    with col_info:
        st.markdown("""
        <div class="card">
            <div class="card-title">ℹ️ คำแนะนำ</div>
            <b>รองรับ:</b><br>
            📄 PDF — text layer + OCR<br>
            🖼️ PNG / JPG / JPEG<br><br>
            <b>OCR Engine:</b><br>
            🔍 Tesseract (tha+eng)<br>
            📐 PyMuPDF direct text<br><br>
            <b>ผลลัพธ์:</b><br>
            ✅ Segments แบ่งพร้อมใช้<br>
            ✅ CSV สำหรับ CAT Tools<br>
            ✅ Glossary อัตโนมัติ<br>
            ✅ บันทึกประวัติอัตโนมัติ
        </div>
        """, unsafe_allow_html=True)

    # ── Process ──────────────────────────────────────────────────────────────
    if extract_btn and uploaded:
        lang      = LANG_MAP[lang_choice]
        ocr_lang  = get_tesseract_lang(lang)
        file_bytes = uploaded.read()
        ftype      = uploaded.name.rsplit(".", 1)[-1].lower()

        prog   = st.progress(0, text="กำลังเตรียมไฟล์…")
        status = st.empty()

        try:
            # 1. OCR / text extraction
            status.info("🔍 กำลังถอดข้อความ…")
            prog.progress(15, text="อ่านไฟล์…")
            if ftype == "pdf":
                pages_text = extract_text_from_pdf(file_bytes, lang=ocr_lang)
            else:
                pages_text = [extract_text_from_image(file_bytes, lang=ocr_lang)]

            # 2. Segment
            status.info("✂️ กำลังแบ่ง segments…")
            prog.progress(45, text="แบ่ง segments…")
            segments = process_extracted_text(pages_text, lang=lang)

            # 3. Glossary
            status.info("📚 กำลังสร้าง Glossary…")
            prog.progress(65, text="สร้าง Glossary…")
            glossary = extract_glossary(segments, lang=lang, min_freq=min_freq)

            # 4. Save
            status.info("💾 กำลังบันทึก…")
            prog.progress(85, text="บันทึกโปรเจกต์…")
            pid = save_project(
                user_id=st.session_state.user["id"],
                name=proj_name,
                file_name=uploaded.name,
                file_type=ftype,
                language=lang,
                segments=segments,
                glossary_terms=glossary,
            )

            prog.progress(100, text="เสร็จสิ้น!")
            status.success(
                f"✅ ถอดข้อความสำเร็จ! "
                f"พบ **{len(segments)}** segments และ **{len(glossary)}** คำใน Glossary"
            )

            st.session_state.result = {
                "project_id":   pid,
                "project_name": proj_name,
                "segments":      segments,
                "glossary":      glossary,
                "file_name":    uploaded.name,
                "language":      lang,
            }

            c1, c2 = st.columns(2)
            with c1:
                if st.button("📋  ดูผลลัพธ์ →", use_container_width=True):
                    st.session_state.page = "results"
                    st.rerun()
            with c2:
                if st.button("📚  ดู Glossary →", use_container_width=True):
                    st.session_state.page = "glossary"
                    st.rerun()

        except Exception as exc:
            prog.empty()
            status.error(f"❌ เกิดข้อผิดพลาด: {exc}")
            with st.expander("รายละเอียดข้อผิดพลาด"):
                st.exception(exc)


# ═════════════════════════════════════════════════════════════════════════════
#  PAGE — RESULTS
# ═════════════════════════════════════════════════════════════════════════════

def page_results():
    hero(
        "📋 ผลลัพธ์การถอดข้อความ",
        "ตรวจสอบ segments และดาวน์โหลด CSV สำหรับ CAT Tools",
        mono="step 2 of 3 — review",
    )
    result = st.session_state.result

    if not result:
        st.info("⚠️ ยังไม่มีผลลัพธ์ — กรุณาอัปโหลดไฟล์ก่อน")
        if st.button("ไปหน้าอัปโหลด"):
            st.session_state.page = "upload"
            st.rerun()
        return

    segments = result["segments"]
    lang     = result["language"]

    # ── Stats ─────────────────────────────────────────────────────────────
    total_ch = sum(len(s) for s in segments)
    st.markdown(f"""
    <div class="stats-row">
        <div class="stat">
            <div class="stat-n">{len(segments)}</div>
            <div class="stat-lbl">📝 Segments</div>
        </div>
        <div class="stat">
            <div class="stat-n">{total_ch:,}</div>
            <div class="stat-lbl">🔤 ตัวอักษร</div>
        </div>
        <div class="stat">
            <div class="stat-n">{len(result.get('glossary', []))}</div>
            <div class="stat-lbl">📚 Glossary terms</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Downloads ─────────────────────────────────────────────────────────
    c1, c2 = st.columns(2)
    pname = result["project_name"]
    with c1:
        st.download_button(
            "⬇️  ดาวน์โหลด CSV (Segments)",
            data=make_segments_csv(segments, lang),
            file_name=f"{pname}_segments.csv",
            mime="text/csv",
            use_container_width=True,
        )
    with c2:
        if result.get("glossary"):
            st.download_button(
                "⬇️  ดาวน์โหลด CSV (Glossary)",
                data=make_glossary_csv(result["glossary"]),
                file_name=f"{pname}_glossary.csv",
                mime="text/csv",
                use_container_width=True,
            )

    # ── Segment viewer ────────────────────────────────────────────────────
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="card-title">📝 Segments</div>', unsafe_allow_html=True)

    col_search, col_pp = st.columns([3, 1])
    with col_search:
        q = st.text_input("🔍 ค้นหา", placeholder="พิมพ์ข้อความที่ต้องการ…", label_visibility="collapsed")
    with col_pp:
        page_size = st.selectbox("แสดง", [20, 50, 100], index=0, label_visibility="collapsed")

    filtered = [s for s in segments if q.lower() in s.lower()] if q else segments
    if q:
        st.caption(f"พบ {len(filtered)} จาก {len(segments)} segments")

    total_pages = max(1, (len(filtered) + page_size - 1) // page_size)
    pg = st.number_input("หน้า", 1, total_pages, 1, label_visibility="collapsed") - 1
    start, end = pg * page_size, min((pg + 1) * page_size, len(filtered))

    for i, seg in enumerate(filtered[start:end], start=start):
        badge = lang_badge(
            "thai" if any("\u0e00" <= c <= "\u0e7f" for c in seg) else "english"
        )
        st.markdown(f"""
        <div class="seg">
            <span class="seg-id">SEG_{i+1:04d} &nbsp; {badge}</span>
            {seg}
        </div>""", unsafe_allow_html=True)

    if total_pages > 1:
        st.caption(f"หน้า {pg+1} / {total_pages}")

    st.markdown("</div>", unsafe_allow_html=True)


# ═════════════════════════════════════════════════════════════════════════════
#  PAGE — GLOSSARY
# ═════════════════════════════════════════════════════════════════════════════

def page_glossary():
    hero(
        "📚 Glossary",
        "คำศัพท์ที่พบบ่อย — tokenize ถูกต้อง กรอง stop word แล้ว",
        mono="step 3 of 3 — glossary",
    )
    result = st.session_state.result

    if not result or not result.get("glossary"):
        st.info("⚠️ ยังไม่มี Glossary — กรุณาถอดข้อความก่อน")
        return

    glossary = result["glossary"]
    pname    = result["project_name"]

    top_freq = glossary[0][1] if glossary else 1

    # Stats
    st.markdown(f"""
    <div class="stats-row">
        <div class="stat">
            <div class="stat-n">{len(glossary)}</div>
            <div class="stat-lbl">📚 คำทั้งหมด</div>
        </div>
        <div class="stat">
            <div class="stat-n">{top_freq}</div>
            <div class="stat-lbl">🔝 ความถี่สูงสุด</div>
        </div>
        <div class="stat">
            <div class="stat-n">{sum(f for _,f in glossary)}</div>
            <div class="stat-lbl">∑ รวมความถี่</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Download
    st.download_button(
        "⬇️  ดาวน์โหลด Glossary CSV",
        data=make_glossary_csv(glossary),
        file_name=f"{pname}_glossary.csv",
        mime="text/csv",
        use_container_width=True,
    )

    # Search + table
    q = st.text_input("🔍 ค้นหาคำ", placeholder="พิมพ์คำ…")
    filtered = [(t, f) for t, f in glossary if q.lower() in t.lower()] if q else glossary

    df = pd.DataFrame(filtered, columns=["คำศัพท์", "ความถี่"])
    df.index = range(1, len(df) + 1)

    st.dataframe(
        df,
        use_container_width=True,
        height=min(600, 40 * len(df) + 40),
        column_config={
            "คำศัพท์": st.column_config.TextColumn("คำศัพท์", width="medium"),
            "ความถี่":  st.column_config.ProgressColumn(
                "ความถี่",
                format="%d ครั้ง",
                min_value=0,
                max_value=top_freq,
            ),
        },
    )


# ═════════════════════════════════════════════════════════════════════════════
#  PAGE — HISTORY
# ═════════════════════════════════════════════════════════════════════════════

def page_history():
    hero(
        "📁 ประวัติโปรเจกต์",
        "โปรเจกต์ทั้งหมดที่คุณเคยทำ — โหลดซ้ำหรือลบได้",
        mono="project history",
    )

    uid      = st.session_state.user["id"]
    projects = get_user_projects(uid)

    if not projects:
        st.info("ยังไม่มีโปรเจกต์ กรุณาอัปโหลดไฟล์เพื่อเริ่มต้น")
        if st.button("ไปหน้าอัปโหลด"):
            st.session_state.page = "upload"
            st.rerun()
        return

    for proj in projects:
        pid   = proj["id"]
        pname = proj["name"]
        fname = proj["file_name"]
        plang = proj["language"]
        pdate = proj["created_at"][:16]
        pseg  = proj["segment_count"]
        pgls  = proj["glossary_count"]

        with st.expander(f"📄  {pname}  ·  {fname}  ·  {pdate}"):
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Segments", pseg)
            c2.metric("Glossary", pgls)
            c3.metric("ภาษา", LANG_LABEL.get(plang, plang).split(" ", 1)[-1])
            c4.metric("ประเภทไฟล์", proj["file_type"].upper())

            ca, cb = st.columns([4, 1])
            with ca:
                if st.button(f"📂  โหลดโปรเจกต์", key=f"load_{pid}", use_container_width=True):
                    segs = get_project_segments(pid)
                    glss = get_project_glossary(pid)
                    st.session_state.result = {
                        "project_id":   pid,
                        "project_name": pname,
                        "segments":      [s["source_text"] for s in segs],
                        "glossary":      [(g["term"], g["frequency"]) for g in glss],
                        "file_name":    fname,
                        "language":      plang,
                    }
                    st.session_state.page = "results"
                    st.rerun()
            with cb:
                if st.button(f"🗑️", key=f"del_{pid}", help="ลบโปรเจกต์", use_container_width=True, type="secondary"):
                    if delete_project(pid, uid):
                        st.success("ลบโปรเจกต์เรียบร้อย")
                        st.rerun()
                    else:
                        st.error("ไม่สามารถลบได้")


# ═════════════════════════════════════════════════════════════════════════════
#  ROUTER
# ═════════════════════════════════════════════════════════════════════════════

def main():
    if not st.session_state.user:
        page_auth()
        return

    show_sidebar()

    page = st.session_state.page
    if   page == "upload":   page_upload()
    elif page == "results":  page_results()
    elif page == "glossary": page_glossary()
    elif page == "history":  page_history()
    else:                    page_upload()


if __name__ == "__main__":
    main()

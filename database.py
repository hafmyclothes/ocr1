import sqlite3
import json

def get_connection():
    # ใช้ check_same_thread=False เพื่อให้รันบน Streamlit ได้เสถียร
    return sqlite3.connect("users.db", check_same_thread=False)

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    # 1. ตาราง Users
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # 2. ตาราง Projects (เพิ่มคอลัมน์ภาษาและ Glossary แบบ JSON)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            name TEXT,
            file_name TEXT,
            file_type TEXT,
            language TEXT,
            glossary_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)
    
    # 3. ตาราง Segments
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS segments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            original_text TEXT,
            translated_text TEXT,
            FOREIGN KEY(project_id) REFERENCES projects(id)
        )
    """)
    conn.commit()
    conn.close()

def create_user(username, email, hashed_password):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO users (username, email, password) VALUES (?, ?, ?)", 
                       (username, email, hashed_password))
        conn.commit()
        return True, "ลงทะเบียนสำเร็จ"
    except sqlite3.IntegrityError:
        return False, "ชื่อผู้ใช้หรืออีเมลนี้ถูกใช้งานแล้ว"
    finally:
        conn.close()

def get_user_by_username(username):
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    return dict(user) if user else None

def get_user_stats(user_id):
    conn = get_connection()
    # นับโครงการ
    count_projects = conn.execute("SELECT COUNT(*) FROM projects WHERE user_id = ?", (user_id,)).fetchone()[0]
    # นับ segments รวมทั้งหมดของผู้ใช้
    try:
        count_segments = conn.execute("""
            SELECT COUNT(*) FROM segments 
            JOIN projects ON segments.project_id = projects.id 
            WHERE projects.user_id = ?
        """, (user_id,)).fetchone()[0]
    except:
        count_segments = 0
    conn.close()
    return {"total_projects": count_projects, "total_segments": count_segments}

def save_project(user_id, name, file_name, file_type, language, segments=None, glossary_terms=None):
    conn = get_connection()
    cursor = conn.cursor()
    
    # แปลง Glossary เป็น JSON string เพื่อเก็บใน Text column
    glossary_json = json.dumps(glossary_terms) if glossary_terms else None
    
    cursor.execute("""
        INSERT INTO projects (user_id, name, file_name, file_type, language, glossary_json) 
        VALUES (?, ?, ?, ?, ?, ?)
    """, (user_id, name, file_name, file_type, language, glossary_json))
    
    project_id = cursor.lastrowid
    
    # บันทึกแต่ละ Segment ลงตาราง segments
    if segments:
        for seg in segments:
            cursor.execute("INSERT INTO segments (project_id, original_text) VALUES (?, ?)", 
                           (project_id, seg))
            
    conn.commit()
    conn.close()
    return project_id

def get_user_projects(user_id):
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    # ดึงรายชื่อโปรเจกต์พร้อมนับจำนวน segment และ glossary ในตัวเดียว
    query = """
        SELECT p.*, 
               (SELECT COUNT(*) FROM segments WHERE project_id = p.id) as segment_count
        FROM projects p 
        WHERE p.user_id = ? 
        ORDER BY p.created_at DESC
    """
    rows = conn.execute(query, (user_id,)).fetchall()
    conn.close()
    
    projects = []
    for r in rows:
        d = dict(r)
        # คำนวณจำนวน glossary จาก JSON string
        gls = json.loads(d['glossary_json']) if d['glossary_json'] else []
        d['glossary_count'] = len(gls)
        projects.append(d)
    return projects

def get_project_segments(project_id):
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    # ใช้ 'source_text' ตามที่หน้า history ใน app.py เรียกใช้
    rows = conn.execute("SELECT id, original_text as source_text FROM segments WHERE project_id = ?", (project_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_project_glossary(project_id):
    conn = get_connection()
    res = conn.execute("SELECT glossary_json FROM projects WHERE id = ?", (project_id,)).fetchone()
    conn.close()
    # ส่งคืนเป็น list of lists/tuples ตามที่แอปต้องการ
    return json.loads(res[0]) if res and res[0] else []

def delete_project(project_id, user_id):
    conn = get_connection()
    try:
        # ลบ segments ก่อน (Foreign Key)
        conn.execute("DELETE FROM segments WHERE project_id = ?", (project_id,))
        # ลบโปรเจกต์ (เช็ค user_id เพื่อความปลอดภัย)
        conn.execute("DELETE FROM projects WHERE id = ? AND user_id = ?", (project_id, user_id))
        conn.commit()
        return True
    except:
        return False
    finally:
        conn.close()

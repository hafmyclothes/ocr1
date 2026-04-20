import sqlite3
import json

def get_connection():
    return sqlite3.connect("users.db", check_same_thread=False)

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    # ตาราง Users
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # ตาราง Projects (เพิ่มคอลัมน์ glossary_json และ language)
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
    
    # ตาราง Segments
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

def save_project(user_id, name, file_name, file_type, language, segments=None, glossary_terms=None):
    conn = get_connection()
    cursor = conn.cursor()
    
    # แปลง dictionary เป็น string เพื่อเก็บในฐานข้อมูล
    glossary_json = json.dumps(glossary_terms) if glossary_terms else None
    
    cursor.execute(
        "INSERT INTO projects (user_id, name, file_name, file_type, language, glossary_json) VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, name, file_name, file_type, language, glossary_json)
    )
    project_id = cursor.lastrowid
    
    if segments:
        for seg in segments:
            cursor.execute(
                "INSERT INTO segments (project_id, original_text) VALUES (?, ?)",
                (project_id, seg)
            )
            
    conn.commit()
    conn.close()
    return project_id

# ฟังก์ชันอื่นๆ (get_user_stats, get_user_projects ฯลฯ) ให้คงไว้ตามเดิม
def get_user_stats(user_id):
    conn = get_connection()
    count_projects = conn.execute("SELECT COUNT(*) FROM projects WHERE user_id = ?", (user_id,)).fetchone()[0]
    try:
        count_segments = conn.execute("SELECT COUNT(*) FROM segments JOIN projects ON segments.project_id = projects.id WHERE projects.user_id = ?", (user_id,)).fetchone()[0]
    except:
        count_segments = 0
    conn.close()
    return {"total_projects": count_projects, "total_segments": count_segments}

def get_user_by_username(username):
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    return dict(user) if user else None

def create_user(username, email, hashed_password):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO users (username, email, password) VALUES (?, ?, ?)", (username, email, hashed_password))
        conn.commit()
        return True, "ลงทะเบียนสำเร็จ"
    except sqlite3.IntegrityError:
        return False, "ชื่อผู้ใช้หรืออีเมลนี้ถูกใช้งานแล้ว"
    finally:
        conn.close()

def get_user_projects(user_id):
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    projects = conn.execute("SELECT * FROM projects WHERE user_id = ? ORDER BY created_at DESC", (user_id,)).fetchall()
    conn.close()
    return [dict(p) for p in projects]

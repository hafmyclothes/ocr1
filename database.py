import sqlite3

def get_connection():
    # กำหนด check_same_thread=False เพื่อให้ใช้งานบน Streamlit ได้
    return sqlite3.connect("users.db", check_same_thread=False)

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    # สร้างตาราง Users
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # สร้างตาราง Projects
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            name TEXT,
            file_name TEXT,
            file_type TEXT,
            language TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)
    conn.commit()
    conn.close()

def create_user(username, email, hashed_password):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO users (username, email, password) VALUES (?, ?, ?)",
            (username, email, hashed_password)
        )
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

def get_user_projects(user_id):
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    projects = conn.execute("SELECT * FROM projects WHERE user_id = ? ORDER BY created_at DESC", (user_id,)).fetchall()
    conn.close()
    return [dict(p) for p in projects]

def get_user_stats(user_id):
    conn = get_connection()
    count = conn.execute("SELECT COUNT(*) FROM projects WHERE user_id = ?", (user_id,)).fetchone()[0]
    conn.close()
    return {"total_projects": count}

# เพิ่มฟังก์ชันอื่นๆ เพื่อให้แอปไม่พังเวลาเรียกใช้งานส่วนลึกๆ
def get_project_segments(project_id): return []
def get_project_glossary(project_id): return []
def save_project(user_id, name, file_name, file_type, lang):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO projects (user_id, name, file_name, file_type, language) VALUES (?, ?, ?, ?, ?)",
        (user_id, name, file_name, file_type, lang)
    )
    conn.commit()
    conn.close()
def delete_project(project_id): pass

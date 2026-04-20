"""
database.py — SQLite persistence layer
ข้อมูลผู้ใช้, โปรเจกต์, segments และ glossary terms
"""
import sqlite3
import os
from datetime import datetime

DB_PATH = "thai_extractor.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    """สร้างตารางถ้ายังไม่มี"""
    conn = get_connection()
    c = conn.cursor()

    c.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            username      TEXT UNIQUE NOT NULL,
            email         TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS projects (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id       INTEGER NOT NULL,
            name          TEXT NOT NULL,
            file_name     TEXT NOT NULL,
            file_type     TEXT NOT NULL,
            language      TEXT NOT NULL,
            segment_count INTEGER DEFAULT 0,
            glossary_count INTEGER DEFAULT 0,
            created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS segments (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id    INTEGER NOT NULL,
            segment_order INTEGER NOT NULL,
            source_text   TEXT NOT NULL,
            FOREIGN KEY (project_id) REFERENCES projects(id)
        );

        CREATE TABLE IF NOT EXISTS glossary_terms (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id  INTEGER NOT NULL,
            term        TEXT NOT NULL,
            frequency   INTEGER NOT NULL,
            translation TEXT DEFAULT '',
            FOREIGN KEY (project_id) REFERENCES projects(id)
        );
    """)

    conn.commit()
    conn.close()


# ─── User operations ──────────────────────────────────────────────────────────

def create_user(username: str, email: str, password_hash: str) -> bool:
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
            (username, email, password_hash),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def get_user_by_username(username: str):
    conn = get_connection()
    user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    return user


def get_user_by_email(email: str):
    conn = get_connection()
    user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()
    return user


# ─── Project operations ───────────────────────────────────────────────────────

def save_project(
    user_id: int,
    name: str,
    file_name: str,
    file_type: str,
    language: str,
    segments: list,
    glossary_terms: list,
) -> int:
    conn = get_connection()
    c = conn.cursor()

    c.execute(
        """INSERT INTO projects
           (user_id, name, file_name, file_type, language, segment_count, glossary_count)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (user_id, name, file_name, file_type, language, len(segments), len(glossary_terms)),
    )
    project_id = c.lastrowid

    c.executemany(
        "INSERT INTO segments (project_id, segment_order, source_text) VALUES (?, ?, ?)",
        [(project_id, i, seg) for i, seg in enumerate(segments)],
    )

    c.executemany(
        "INSERT INTO glossary_terms (project_id, term, frequency) VALUES (?, ?, ?)",
        [(project_id, term, freq) for term, freq in glossary_terms],
    )

    conn.commit()
    conn.close()
    return project_id


def get_user_projects(user_id: int) -> list:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM projects WHERE user_id = ? ORDER BY created_at DESC",
        (user_id,),
    ).fetchall()
    conn.close()
    return rows


def get_project_segments(project_id: int) -> list:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM segments WHERE project_id = ? ORDER BY segment_order",
        (project_id,),
    ).fetchall()
    conn.close()
    return rows


def get_project_glossary(project_id: int) -> list:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM glossary_terms WHERE project_id = ? ORDER BY frequency DESC",
        (project_id,),
    ).fetchall()
    conn.close()
    return rows


def delete_project(project_id: int, user_id: int) -> bool:
    conn = get_connection()
    project = conn.execute(
        "SELECT id FROM projects WHERE id = ? AND user_id = ?",
        (project_id, user_id),
    ).fetchone()
    if project:
        conn.execute("DELETE FROM segments WHERE project_id = ?", (project_id,))
        conn.execute("DELETE FROM glossary_terms WHERE project_id = ?", (project_id,))
        conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        conn.commit()
        conn.close()
        return True
    conn.close()
    return False


def get_user_stats(user_id: int) -> dict:
    conn = get_connection()
    stats = conn.execute(
        """SELECT COUNT(*) as total_projects,
                  COALESCE(SUM(segment_count), 0)  as total_segments,
                  COALESCE(SUM(glossary_count), 0) as total_glossary
           FROM projects WHERE user_id = ?""",
        (user_id,),
    ).fetchone()
    conn.close()
    return dict(stats) if stats else {"total_projects": 0, "total_segments": 0, "total_glossary": 0}

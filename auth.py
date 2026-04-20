"""
auth.py — ระบบ Login / Register ด้วย bcrypt
"""
import re
import bcrypt
from modules.database import create_user, get_user_by_username, get_user_by_email


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except Exception:
        return False


def register_user(username: str, email: str, password: str) -> tuple[bool, str]:
    username = username.strip()
    email = email.strip().lower()

    if len(username) < 3:
        return False, "ชื่อผู้ใช้ต้องมีอย่างน้อย 3 ตัวอักษร"
    if not re.match(r"^[a-zA-Z0-9_ก-๙]+$", username):
        return False, "ชื่อผู้ใช้ใช้ได้เฉพาะ a-z, 0-9, _ และภาษาไทยเท่านั้น"
    if len(password) < 6:
        return False, "รหัสผ่านต้องมีอย่างน้อย 6 ตัวอักษร"
    if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        return False, "รูปแบบอีเมลไม่ถูกต้อง"
    if get_user_by_username(username):
        return False, "ชื่อผู้ใช้นี้มีอยู่แล้ว"
    if get_user_by_email(email):
        return False, "อีเมลนี้ถูกใช้งานแล้ว"

    pw_hash = hash_password(password)
    ok = create_user(username, email, pw_hash)
    if ok:
        return True, "สมัครสมาชิกสำเร็จ!"
    return False, "เกิดข้อผิดพลาดในการบันทึกข้อมูล"


def login_user(username: str, password: str) -> tuple[bool, str, dict]:
    username = username.strip()
    user = get_user_by_username(username)

    if not user:
        return False, "ไม่พบชื่อผู้ใช้นี้ในระบบ", {}
    if not verify_password(password, user["password_hash"]):
        return False, "รหัสผ่านไม่ถูกต้อง", {}

    return True, "เข้าสู่ระบบสำเร็จ", {
        "id": user["id"],
        "username": user["username"],
        "email": user["email"],
    }

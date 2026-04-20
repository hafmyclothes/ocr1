import re
import bcrypt
# แก้ไขจุดนี้: ตัด modules. ออก
from database import create_user, get_user_by_username, get_user_by_email

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def check_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def validate_email(email: str) -> bool:
    return bool(re.match(r"[^@]+@[^@]+\.[^@]+", email))

def register_user(username: str, email: str, password: str):
    if len(username) < 3:
        return False, "ชื่อผู้ใช้ต้องมีอย่างน้อย 3 ตัวอักษร"
    if not validate_email(email):
        return False, "รูปแบบอีเมลไม่ถูกต้อง"
    if len(password) < 6:
        return False, "รหัสผ่านต้องมีอย่างน้อย 6 ตัวอักษร"
    
    hashed = hash_password(password)
    return create_user(username, email, hashed)

def login_user(username: str, password: str):
    user = get_user_by_username(username)
    if user and check_password(password, user['password']):
        return True, "เข้าสู่ระบบสำเร็จ", user
    return False, "ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง", None

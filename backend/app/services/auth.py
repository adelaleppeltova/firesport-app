import os
import uuid
from datetime import datetime, timedelta

from argon2 import PasswordHasher
from jose import jwt, JWTError

ph = PasswordHasher()
SECRET_KEY = os.getenv("SECRET_KEY", "replace-with-a-random-secret")
ALGORITHM = "HS256"
ACCESS_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "15"))
REFRESH_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))
PASSWORD_RESET_EXPIRE_MINUTES = int(
    os.getenv("PASSWORD_RESET_EXPIRE_MINUTES", "60")
)

def hash_password(password: str) -> str:
    return ph.hash(password)

def verify_password(hash: str, password: str) -> bool:
    try:
        return ph.verify(hash, password)
    except Exception:
        return False

def create_access_token(user_id: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_EXPIRE_MINUTES)
    to_encode = {"sub": str(user_id), "type": "access", "exp": expire}
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def create_refresh_token(user_id: str) -> dict:
    jti = str(uuid.uuid4())
    expire = datetime.utcnow() + timedelta(days=REFRESH_EXPIRE_DAYS)
    to_encode = {"sub": str(user_id), "jti": jti, "type": "refresh", "exp": expire}
    token = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return {"token": token, "jti": jti, "expires_at": expire}


def create_password_reset_token(user_id: str) -> dict:
    jti = str(uuid.uuid4())
    expire = datetime.utcnow() + timedelta(minutes=PASSWORD_RESET_EXPIRE_MINUTES)
    to_encode = {"sub": str(user_id), "jti": jti, "type": "password_reset", "exp": expire}
    token = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return {"token": token, "jti": jti, "expires_at": expire}

def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise

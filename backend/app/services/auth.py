import os
import uuid
from datetime import datetime, timedelta
from typing import Optional

from argon2 import PasswordHasher
from jose import jwt, JWTError
from bson import ObjectId

from app.db.database import db

ph = PasswordHasher()
SECRET_KEY = os.getenv("SECRET_KEY", "replace-with-a-random-secret")
ALGORITHM = "HS256"
ACCESS_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "15"))
REFRESH_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

users_col = db["users"]

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

def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise

def store_refresh_jti(user_id: str, jti: str, expires_at: datetime):
    users_col.update_one(
        {"_id": ObjectId(user_id)},
        {"$push": {"refresh_tokens": {"jti": jti, "expires_at": expires_at}}},
    )

def remove_refresh_jti(user_id: str, jti: str):
    users_col.update_one(
        {"_id": ObjectId(user_id)},
        {"$pull": {"refresh_tokens": {"jti": jti}}},
    )

def replace_refresh_jti(user_id: str, old_jti: str, new_jti: str, new_expires: datetime):
    users_col.update_one(
        {"_id": ObjectId(user_id)},
        {
            "$pull": {"refresh_tokens": {"jti": old_jti}}
        }
    )
    users_col.update_one(
        {"_id": ObjectId(user_id)},
        {"$push": {"refresh_tokens": {"jti": new_jti, "expires_at": new_expires}}},
    )

def is_jti_valid(user_id: str, jti: str) -> bool:
    u = users_col.find_one({"_id": ObjectId(user_id), "refresh_tokens.jti": jti})
    return u is not None
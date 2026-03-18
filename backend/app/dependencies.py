from fastapi import Depends, HTTPException, Header, status
from pymongo import MongoClient
from bson import ObjectId
import os
import logging

from app.services.auth import decode_token

logger = logging.getLogger(__name__)

# Synchronní PyMongo client pro dependencies
MONGO_URL = os.getenv("MONGO_URL", "mongodb://firesport-mongodb:27017")
sync_client = MongoClient(MONGO_URL)
sync_db = sync_client["firesport"]
users_collection = sync_db["users"]


def get_current_user(authorization: str = Header(None)):
    """
    Synchronní dependency pro získání aktuálního uživatele z JWT tokenu.
    """
    auth_preview = None
    if authorization is not None:
        auth_preview = str(authorization)[:50]
    logger.info(f"get_current_user called with authorization: {auth_preview}...")
    
    if not authorization:
        logger.error("Missing Authorization header")
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    
    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            raise ValueError()
    except Exception as e:
        logger.error(f"Invalid Authorization header format: {e}")
        raise HTTPException(status_code=401, detail="Invalid Authorization header")
    
    try:
        payload = decode_token(token)
        logger.info(f"Token decoded successfully, sub: {payload.get('sub')}")
    except Exception as e:
        logger.error(f"Token decode failed: {e}")
        raise HTTPException(status_code=401, detail="Invalid token")
    
    if payload.get("type") != "access":
        logger.error(f"Invalid token type: {payload.get('type')}")
        raise HTTPException(status_code=401, detail="Invalid token type")
    
    user = users_collection.find_one({"_id": ObjectId(payload.get("sub"))})
    if not user:
        logger.error(f"User not found for id: {payload.get('sub')}")
        raise HTTPException(status_code=401, detail="User not found")
    
    logger.info(f"User found: {user['email']}")
    
    return {
        "id": str(user["_id"]),
        "email": user["email"],
        "role": user.get("role", "user"),
        "is_active": user.get("is_active", True),
        "athlete_id": user.get("athlete_id")
    }


def require_admin(user=Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user

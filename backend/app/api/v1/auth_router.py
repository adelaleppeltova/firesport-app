from datetime import datetime
from fastapi import APIRouter, HTTPException, status, Response, Depends, Request, Header
from fastapi.concurrency import run_in_threadpool
from bson import ObjectId

from app.models.user import UserCreate, UserOut
from app.models.auth import Token
from app.services.auth import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.db.database import db

router = APIRouter(prefix="/auth", tags=["auth"])

users = db["users"]

@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(payload: UserCreate):
    if await users.find_one({"email": payload.email}):
        raise HTTPException(status_code=400, detail="Email already registered")
    hashed = await run_in_threadpool(hash_password, payload.password)
    user_doc = {
        "email": payload.email,
        "hashed_password": hashed,
        "role": "user",
        "is_active": True,
        "created_at": datetime.utcnow(),
        "refresh_tokens": [],
    }
    result = await users.insert_one(user_doc)
    return UserOut(id=str(result.inserted_id), email=payload.email, role="user", is_active=True)

@router.post("/login", response_model=Token)
async def login(response: Response, payload: UserCreate):
    user = await users.find_one({"email": payload.email})
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    # verify password in threadpool
    ok = await run_in_threadpool(verify_password, user.get("hashed_password", ""), payload.password)
    if not ok:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    user_id = str(user["_id"])
    access_token = create_access_token(user_id)
    refresh = create_refresh_token(user_id)
    # store refresh jti
    await users.update_one(
        {"_id": ObjectId(user_id)},
        {"$push": {"refresh_tokens": {"jti": refresh["jti"], "expires_at": refresh["expires_at"]}}},
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh["token"],
        httponly=True,
        samesite="lax",
        secure=False,
        expires=int((refresh["expires_at"] - datetime.utcnow()).total_seconds()),
    )
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/refresh", response_model=Token)
async def refresh(request: Request, response: Response):
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(status_code=401, detail="Missing refresh token")
    try:
        payload = decode_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid token type")
    user_id = payload.get("sub")
    jti = payload.get("jti")
    # check jti in DB
    u = await users.find_one({"_id": ObjectId(user_id), "refresh_tokens.jti": jti})
    if not u:
        raise HTTPException(status_code=401, detail="Refresh token revoked")
    # rotate
    new_refresh = create_refresh_token(user_id)
    await users.update_one({"_id": ObjectId(user_id)}, {"$pull": {"refresh_tokens": {"jti": jti}}})
    await users.update_one({"_id": ObjectId(user_id)}, {"$push": {"refresh_tokens": {"jti": new_refresh["jti"], "expires_at": new_refresh["expires_at"]}}})
    new_access = create_access_token(user_id)
    response.set_cookie(
        key="refresh_token",
        value=new_refresh["token"],
        httponly=True,
        samesite="lax",
        secure=False,
        expires=int((new_refresh["expires_at"] - datetime.utcnow()).total_seconds()),
    )
    return {"access_token": new_access, "token_type": "bearer"}

@router.post("/logout", status_code=204)
async def logout(request: Request, response: Response):
    token = request.cookies.get("refresh_token")
    if token:
        try:
            payload = decode_token(token)
            user_id = payload.get("sub")
            jti = payload.get("jti")
            await users.update_one({"_id": ObjectId(user_id)}, {"$pull": {"refresh_tokens": {"jti": jti}}})
        except Exception:
            pass
    response.delete_cookie("refresh_token")
    return Response(status_code=204)

# async dependency
async def get_current_user(authorization: str = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            raise ValueError()
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid Authorization header")
    try:
        payload = decode_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")
    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Invalid token type")
    user = await users.find_one({"_id": ObjectId(payload.get("sub"))})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return {
        "id": str(user["_id"]), 
        "email": user["email"], 
        "role": user.get("role", "user"), 
        "is_active": user.get("is_active", True),
        "athlete_id": user.get("athlete_id")
    }

@router.get("/me")
async def me(current=Depends(get_current_user)):
    return current

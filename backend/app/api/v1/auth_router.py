from datetime import datetime
from fastapi import APIRouter, HTTPException, status, Response, Depends, Request
from fastapi.concurrency import run_in_threadpool
from bson import ObjectId

from app.models.user import (
    UserRegisterRequest,
    UserLoginRequest,
    UserOut,
    AuthenticatedUserOut,
)
from app.models.auth import (
    Token,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    MessageResponse,
)
from app.services.auth import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    create_password_reset_token,
    decode_token,
)
from app.services.email_service import send_password_reset_email
from app.db.database import db
from app.dependencies import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])

users = db["users"]

@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(payload: UserRegisterRequest):
    if await users.find_one({"email": payload.email}):
        raise HTTPException(status_code=400, detail="Email already registered")
    hashed = await run_in_threadpool(hash_password, payload.password_hash)
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
async def login(response: Response, payload: UserLoginRequest):
    user = await users.find_one({"email": payload.email})
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    user_id = str(user["_id"])
    stored_password_hash = user.get("hashed_password", "")
    ok = await run_in_threadpool(verify_password, stored_password_hash, payload.password_hash)

    if not ok:
        raise HTTPException(status_code=401, detail="Invalid credentials")
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


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(payload: ForgotPasswordRequest):
    generic_message = (
        "Pokud učet s tímto emailem existuje, poslali jsme instrukce pro obnovení hesla."
    )
    user = await users.find_one({"email": payload.email})
    if not user:
        return {"message": generic_message}

    user_id = str(user["_id"])
    reset_token = create_password_reset_token(user_id)
    await users.update_one(
        {"_id": ObjectId(user_id)},
        {
            "$set": {
                "password_reset_jti": reset_token["jti"],
                "password_reset_expires_at": reset_token["expires_at"],
            }
        },
    )

    await run_in_threadpool(
        send_password_reset_email,
        payload.email,
        reset_token["token"],
    )
    return {"message": generic_message}


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(payload: ResetPasswordRequest, response: Response):
    try:
        token_payload = decode_token(payload.token)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    if token_payload.get("type") != "password_reset":
        raise HTTPException(status_code=400, detail="Invalid reset token type")

    user_id = token_payload.get("sub")
    jti = token_payload.get("jti")
    if not user_id or not jti:
        raise HTTPException(status_code=400, detail="Invalid reset token")

    user = await users.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=400, detail="Invalid reset token")

    expires_at = user.get("password_reset_expires_at")
    if (
        user.get("password_reset_jti") != jti
        or expires_at is None
        or expires_at < datetime.utcnow()
    ):
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    new_password_hash = await run_in_threadpool(hash_password, payload.password_hash)
    await users.update_one(
        {"_id": ObjectId(user_id)},
        {
            "$set": {
                "hashed_password": new_password_hash,
                "refresh_tokens": [],
            },
            "$unset": {
                "password_reset_jti": "",
                "password_reset_expires_at": "",
            },
        },
    )
    response.delete_cookie("refresh_token")
    return {"message": "Heslo bylo uspesne obnoveno."}

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

@router.get("/me", response_model=AuthenticatedUserOut)
async def me(current=Depends(get_current_user)):
    return current

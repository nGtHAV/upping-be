import uuid
import os
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Response, Request, status
from fastapi.responses import JSONResponse
from database import (
    create_user, get_user_by_email, get_user_by_id, update_user,
    store_refresh_token, get_refresh_token, delete_refresh_token, delete_all_user_refresh_tokens
)
from auth import (
    hash_password, verify_password, create_access_token, create_refresh_token,
    get_current_user, REFRESH_TOKEN_EXPIRE_DAYS
)
from models import UserRegister, UserLogin, UserUpdate, ChangePassword

router = APIRouter(prefix="/api/auth", tags=["auth"])
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "false").lower() == "true"


def _hash_refresh_token(raw: str) -> str:
    """SHA-256 hash of a refresh token for DB storage/lookup.
    We use SHA-256 (not bcrypt) because we need deterministic lookups."""
    return hashlib.sha256(raw.encode()).hexdigest()


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(user_in: UserRegister):
    if len(user_in.password) < 8:
        raise HTTPException(status_code=422, detail="Password must be at least 8 characters long")
    if get_user_by_email(user_in.email):
        raise HTTPException(status_code=409, detail="Email already registered")
    
    user_id = str(uuid.uuid4())
    pw_hash = hash_password(user_in.password)
    now = datetime.now(timezone.utc).isoformat()
    # Default full_name to empty string if it's None.
    user = create_user(user_id, user_in.email, pw_hash, user_in.full_name or "", now)
    
    return {
        "message": "Registered successfully",
        "user": {k: v for k, v in user.items() if k != "password_hash"}
    }

@router.post("/login")
def login(user_in: UserLogin, response: Response):
    """Login with JSON body: { email, password }."""
    user = get_user_by_email(user_in.email)
    if not user or not verify_password(user_in.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    access_token = create_access_token({"sub": user["id"]})
    raw_refresh = create_refresh_token()
    token_hash = _hash_refresh_token(raw_refresh)
    
    now = datetime.now(timezone.utc)
    expires = (now + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)).isoformat()
    token_id = str(uuid.uuid4())
    store_refresh_token(token_id, user["id"], token_hash, expires, now.isoformat())
    
    response.set_cookie(
        key="refresh_token", value=raw_refresh, httponly=True,
        samesite="lax", secure=COOKIE_SECURE, max_age=REFRESH_TOKEN_EXPIRE_DAYS * 86400
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {k: v for k, v in user.items() if k != "password_hash"}
    }

@router.post("/refresh")
def refresh(request: Request, response: Response):
    raw_refresh = request.cookies.get("refresh_token")
    if not raw_refresh:
        raise HTTPException(status_code=401, detail="Refresh token missing")
    
    token_hash = _hash_refresh_token(raw_refresh)
    rt_record = get_refresh_token(token_hash)
    if not rt_record:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
        
    if datetime.fromisoformat(rt_record["expires_at"]) < datetime.now(timezone.utc):
        delete_refresh_token(token_hash)
        raise HTTPException(status_code=401, detail="Refresh token expired")
        
    user = get_user_by_id(rt_record["user_id"])
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    
    # Token rotation: delete old, create new
    delete_refresh_token(token_hash)
    
    new_raw_refresh = create_refresh_token()
    new_token_hash = _hash_refresh_token(new_raw_refresh)
    now = datetime.now(timezone.utc)
    expires = (now + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)).isoformat()
    store_refresh_token(str(uuid.uuid4()), user["id"], new_token_hash, expires, now.isoformat())
    
    response.set_cookie(
        key="refresh_token", value=new_raw_refresh, httponly=True,
        samesite="lax", secure=COOKIE_SECURE, max_age=REFRESH_TOKEN_EXPIRE_DAYS * 86400
    )
    
    access_token = create_access_token({"sub": user["id"]})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {k: v for k, v in user.items() if k != "password_hash"}
    }

@router.post("/logout")
def logout(request: Request, response: Response):
    raw_refresh = request.cookies.get("refresh_token")
    if raw_refresh:
        token_hash = _hash_refresh_token(raw_refresh)
        delete_refresh_token(token_hash)
    response.delete_cookie("refresh_token")
    return {"message": "Logged out"}

@router.get("/me")
def get_me(current_user: Annotated[dict, Depends(get_current_user)]):
    return {k: v for k, v in current_user.items() if k != "password_hash"}

@router.patch("/me")
def update_me(update_data: UserUpdate, current_user: Annotated[dict, Depends(get_current_user)]):
    now = datetime.now(timezone.utc).isoformat()
    user = update_user(current_user["id"], full_name=update_data.full_name, updated_at=now)
    return {k: v for k, v in user.items() if k != "password_hash"}

@router.post("/change-password")
def change_password(data: ChangePassword, request: Request, response: Response, current_user: Annotated[dict, Depends(get_current_user)]):
    if not verify_password(data.current_password, current_user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid current password")
    
    if len(data.new_password) < 8:
        raise HTTPException(status_code=422, detail="Password must be at least 8 characters long")
    
    now = datetime.now(timezone.utc).isoformat()
    new_hash = hash_password(data.new_password)
    update_user(current_user["id"], password_hash=new_hash, updated_at=now)
    
    delete_all_user_refresh_tokens(current_user["id"])
    response.delete_cookie("refresh_token")
    
    return {"message": "Password changed. Please log in again."}

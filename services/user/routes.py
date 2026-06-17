import os
import uuid
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from jose import jwt
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher
from services.user.db import get_db
from services.user.models import User
from services.user.schemas import UserCreate, UserPublic, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])
_pwd = PasswordHash([Argon2Hasher()])
SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production")
ALGORITHM = "HS256"

def hash_password(p): return _pwd.hash(p)
def verify_password(plain, hashed): return _pwd.verify(plain, hashed)
def make_token(sub, type_, minutes):
    exp = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    return jwt.encode({"sub": str(sub), "exp": exp, "type": type_}, SECRET_KEY, algorithm=ALGORITHM)

@router.post("/register", response_model=UserPublic, status_code=201)
async def register(data: UserCreate, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(User).where(User.email == data.email.lower()))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")
    user = User(
        email=data.email.lower(),
        full_name=data.full_name,
        hashed_password=hash_password(data.password),
        role=data.role,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user

@router.post("/login", response_model=TokenResponse)
async def login(form: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == form.username.lower()))
    user = result.scalar_one_or_none()
    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return TokenResponse(
        access_token=make_token(user.id, "access", 60),
        refresh_token=make_token(user.id, "refresh", 60 * 24 * 7),
    )

@router.get("/me", response_model=UserPublic)
async def get_me(token: str = Depends(lambda: None), db: AsyncSession = Depends(get_db)):
    raise HTTPException(status_code=501, detail="Use /validate endpoint for inter-service auth")

@router.get("/validate/{user_id}", response_model=UserPublic)
async def validate_user(user_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Internal endpoint — called by other services to validate a user ID."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=404, detail="User not found")
    return user

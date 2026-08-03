"""Authentication endpoints (root-level to match the Next.js proxy contract)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.store import UserStore
from app.auth.tokens import (
    DEFAULT_TTL_SECONDS,
    REMEMBER_TTL_SECONDS,
    create_session_token,
    verify_session_token,
)
from app.db.base import get_session

router = APIRouter(tags=["auth"])


class LoginBody(BaseModel):
    username: str
    password: str
    remember: bool = False


class VerifyBody(BaseModel):
    token: str


@router.post("/auth/login")
async def login(
    body: LoginBody, session: AsyncSession = Depends(get_session)
) -> dict:
    store = UserStore(session)
    await store.ensure_seeded()
    if not await store.verify(body.username.strip(), body.password):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    ttl = REMEMBER_TTL_SECONDS if body.remember else DEFAULT_TTL_SECONDS
    token = create_session_token(body.username.strip(), ttl)
    return {
        "token": token,
        "username": body.username.strip(),
        "expires_in": ttl,
        "remember": body.remember,
    }


@router.post("/auth/verify")
async def verify(body: VerifyBody) -> dict:
    payload = verify_session_token(body.token)
    return {
        "authenticated": payload is not None,
        "username": payload["username"] if payload else None,
    }

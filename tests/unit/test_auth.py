"""Tests for backend authentication: passwords, tokens, and the user store."""

from __future__ import annotations

import time

import pytest

from app.auth.passwords import hash_password, verify_password
from app.auth.store import UserStore
from app.auth.tokens import (
    DEFAULT_TTL_SECONDS,
    create_session_token,
    verify_session_token,
)


def test_password_hash_roundtrip():
    encoded = hash_password("s3cret-pass")
    assert encoded.startswith("pbkdf2_sha256$")
    assert verify_password("s3cret-pass", encoded)
    assert not verify_password("wrong", encoded)


def test_password_hash_is_salted():
    a = hash_password("same")
    b = hash_password("same")
    assert a != b  # unique salt per hash
    assert verify_password("same", a)
    assert verify_password("same", b)


def test_verify_password_rejects_malformed():
    assert not verify_password("x", "not-a-valid-hash")
    assert not verify_password("x", "")


def test_token_roundtrip():
    token = create_session_token("admin", DEFAULT_TTL_SECONDS)
    payload = verify_session_token(token)
    assert payload is not None
    assert payload["username"] == "admin"
    assert payload["exp"] > int(time.time())


def test_token_rejects_tamper():
    token = create_session_token("admin")
    body, sig = token.split(".", 1)
    assert verify_session_token(f"{body}.{sig}x") is None  # bad signature
    assert verify_session_token("garbage") is None
    assert verify_session_token(None) is None


def test_token_rejects_expired():
    token = create_session_token("admin", ttl_seconds=-10)
    assert verify_session_token(token) is None


@pytest.mark.asyncio
async def test_user_store_create_and_verify(db_session):
    store = UserStore(db_session)
    await store.create("trader", "hunter2")
    assert await store.verify("trader", "hunter2")
    assert not await store.verify("trader", "nope")
    assert not await store.verify("ghost", "hunter2")


@pytest.mark.asyncio
async def test_user_store_ensure_seeded(db_session):
    store = UserStore(db_session)
    assert await store.get("admin") is None
    await store.ensure_seeded()
    admin = await store.get("admin")
    assert admin is not None
    # Password is stored hashed, never in plaintext.
    assert "atlas" not in admin.password_hash
    assert await store.verify("admin", "atlas")
    # Idempotent — a second call does not create a duplicate or raise.
    await store.ensure_seeded()

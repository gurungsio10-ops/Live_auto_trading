"""Password hashing using PBKDF2-HMAC-SHA256 (stdlib, no external deps)."""

from __future__ import annotations

import hashlib
import hmac
import os

_ALGORITHM = "pbkdf2_sha256"
_ITERATIONS = 200_000
_SALT_BYTES = 16


def hash_password(password: str, *, iterations: int = _ITERATIONS) -> str:
    """Return an encoded hash: ``pbkdf2_sha256$iterations$salt_hex$hash_hex``."""
    salt = os.urandom(_SALT_BYTES)
    derived = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    return f"{_ALGORITHM}${iterations}${salt.hex()}${derived.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    """Constant-time verification of a password against an encoded hash."""
    try:
        algorithm, iterations_s, salt_hex, hash_hex = encoded.split("$")
        iterations = int(iterations_s)
        salt = bytes.fromhex(salt_hex)
    except (ValueError, AttributeError):
        return False
    if algorithm != _ALGORITHM:
        return False
    derived = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    return hmac.compare_digest(derived.hex(), hash_hex)

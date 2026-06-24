"""Password hashing via PBKDF2-HMAC-SHA256 (stdlib + cryptography — no extra deps)."""

from __future__ import annotations

import hashlib
import hmac
import secrets

_ITERATIONS = 260_000
_SALT_BYTES = 16


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(_SALT_BYTES)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _ITERATIONS)
    return f"pbkdf2_sha256${_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iter_str, salt_hex, digest_hex = stored.split("$", 3)
    except ValueError:
        return False
    if algo != "pbkdf2_sha256":
        return False
    salt = bytes.fromhex(salt_hex)
    expected = bytes.fromhex(digest_hex)
    actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, int(iter_str))
    return hmac.compare_digest(actual, expected)

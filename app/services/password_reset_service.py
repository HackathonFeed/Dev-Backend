"""
In-memory password-reset OTP store.

Flow:
  1. POST /auth/forgot-password → generates a 6-digit code, stores it (15-min TTL), sends email
  2. POST /auth/verify-reset-code → checks code, returns a single-use reset_token (30-min TTL)
  3. POST /auth/reset-password → consumes reset_token, updates password hash

Everything lives in module-level dicts — simple and zero-dependency.
Codes/tokens are cleared after use or on expiry.
"""
from __future__ import annotations

import random
import secrets
from datetime import datetime, timedelta, timezone
from typing import NamedTuple


class _CodeEntry(NamedTuple):
    code: str
    expires_at: datetime


# email (lowercase) → OTP entry
_reset_codes: dict[str, _CodeEntry] = {}

# reset_token → (email, expires_at)
_reset_tokens: dict[str, tuple[str, datetime]] = {}

CODE_TTL_MINUTES = 15
TOKEN_TTL_MINUTES = 30


def generate_and_store_code(email: str) -> str:
    """Generate a 6-digit OTP for the given email and store it."""
    code = f"{random.randint(0, 999_999):06d}"  # noqa: S311 — not crypto, just OTP display
    _reset_codes[email.lower()] = _CodeEntry(
        code=code,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=CODE_TTL_MINUTES),
    )
    return code


def verify_code_and_issue_token(email: str, code: str) -> str | None:
    """
    Verify the OTP for `email`.
    Returns a single-use reset_token on success, None on failure/expiry.
    The OTP entry is consumed regardless.
    """
    entry = _reset_codes.pop(email.lower(), None)
    if entry is None:
        return None
    if datetime.now(timezone.utc) > entry.expires_at:
        return None
    if entry.code != code.strip():
        return None

    token = secrets.token_urlsafe(32)
    _reset_tokens[token] = (
        email.lower(),
        datetime.now(timezone.utc) + timedelta(minutes=TOKEN_TTL_MINUTES),
    )
    return token


def consume_reset_token(token: str) -> str | None:
    """
    Consume a reset_token (single-use).
    Returns the email on success, None on failure/expiry.
    """
    entry = _reset_tokens.pop(token, None)
    if entry is None:
        return None
    email, expires_at = entry
    if datetime.now(timezone.utc) > expires_at:
        return None
    return email

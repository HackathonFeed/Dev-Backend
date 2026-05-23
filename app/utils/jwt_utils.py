from datetime import date, datetime, timezone

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_token,
)

__all__ = [
    "create_access_token",
    "create_refresh_token",
    "decode_token",
    "verify_token",
]


def utc_today() -> date:
    return datetime.now(timezone.utc).date()

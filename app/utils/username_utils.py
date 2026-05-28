import re
import secrets
import uuid

USERNAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{2,29}$")

RESERVED_USERNAMES = {
    "admin",
    "api",
    "auth",
    "docs",
    "health",
    "leaderboard",
    "login",
    "me",
    "profile",
    "public",
    "register",
    "static",
    "u",
    "users",
}


def normalize_username(value: str) -> str:
    return value.strip().lower()


def is_valid_username(value: str) -> bool:
    normalized = normalize_username(value)
    if value != normalized:
        return False
    if not USERNAME_PATTERN.fullmatch(normalized):
        return False
    return normalized not in RESERVED_USERNAMES


def slugify_username_base(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    slug = re.sub(r"-+", "-", slug)
    if not slug:
        slug = "user"
    if not slug[0].isalnum():
        slug = f"user-{slug}"
    return slug[:24]


def generate_username_candidate(name: str, user_id: uuid.UUID, attempt: int = 0) -> str:
    base = slugify_username_base(name)
    if attempt == 0:
        candidate = base
    elif attempt == 1:
        candidate = f"{base}-{str(user_id).replace('-', '')[:6]}"
    else:
        candidate = f"{base}-{secrets.token_hex(2)}"
    return normalize_username(candidate)[:30]


def validate_username_or_raise(value: str) -> str:
    normalized = normalize_username(value)
    if not is_valid_username(normalized):
        raise ValueError(
            "Username must be 3-30 characters, start with a letter or number, "
            "and use only lowercase letters, numbers, hyphens, or underscores."
        )
    return normalized

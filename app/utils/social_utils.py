import re
from urllib.parse import urlparse

GITHUB_USERNAME_PATTERN = re.compile(r"^[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,37}[a-zA-Z0-9])?$")
LINKEDIN_USERNAME_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{3,100}$")
TWITTER_USERNAME_PATTERN = re.compile(r"^[a-zA-Z0-9_]{1,15}$")
WEBSITE_PATTERN = re.compile(
    r"^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}(?:/[^\s]*)?$"
)


def _strip_or_none(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _reject_url_host(value: str, host_fragment: str, field_label: str) -> str:
    if host_fragment in value.lower():
        raise ValueError(f"{field_label} must be a username only, not a full URL.")
    return value


def normalize_github_username(value: str) -> str:
    cleaned = value.strip().lstrip("@").strip("/")
    cleaned = re.sub(r"^https?://", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^(?:www\.)?github\.com/", "", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.split("/")[0].split("?")[0].strip()
    _reject_url_host(cleaned, "github.com", "GitHub username")
    if not cleaned:
        raise ValueError("GitHub username cannot be empty.")
    if not GITHUB_USERNAME_PATTERN.fullmatch(cleaned):
        raise ValueError(
            "GitHub username must be 1-39 characters and use only letters, numbers, or hyphens."
        )
    return cleaned


def normalize_linkedin_username(value: str) -> str:
    cleaned = value.strip().lstrip("@").strip("/")
    cleaned = re.sub(r"^https?://", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^(?:www\.)?linkedin\.com/in/", "", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.split("/")[0].split("?")[0].strip()
    _reject_url_host(cleaned, "linkedin.com", "LinkedIn username")
    if not cleaned:
        raise ValueError("LinkedIn username cannot be empty.")
    if not LINKEDIN_USERNAME_PATTERN.fullmatch(cleaned):
        raise ValueError(
            "LinkedIn username must be 3-100 characters and use only letters, numbers, hyphens, or underscores."
        )
    return cleaned


def normalize_twitter_username(value: str) -> str:
    cleaned = value.strip().lstrip("@").strip("/")
    cleaned = re.sub(r"^https?://", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^(?:www\.)?(?:twitter|x)\.com/", "", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.split("/")[0].split("?")[0].strip()
    if "twitter.com" in cleaned.lower() or "x.com" in cleaned.lower():
        raise ValueError("Twitter username must be a username only, not a full URL.")
    if not cleaned:
        raise ValueError("Twitter username cannot be empty.")
    if not TWITTER_USERNAME_PATTERN.fullmatch(cleaned):
        raise ValueError(
            "Twitter username must be 1-15 characters and use only letters, numbers, or underscores."
        )
    return cleaned


def normalize_website(value: str) -> str:
    cleaned = _strip_or_none(value)
    if cleaned is None:
        raise ValueError("Website cannot be empty.")

    if "://" in cleaned:
        parsed = urlparse(cleaned if "://" in cleaned else f"https://{cleaned}")
        host = (parsed.netloc or "").lower().removeprefix("www.")
        path = (parsed.path or "").rstrip("/")
        if not host:
            raise ValueError("Website must be a valid domain or URL.")
        normalized = f"{host}{path}" if path else host
    else:
        normalized = cleaned.removeprefix("www.").rstrip("/")

    if not WEBSITE_PATTERN.fullmatch(normalized):
        raise ValueError("Website must be a valid domain or URL.")
    return normalized


def parse_github_username(value: str | None) -> str | None:
    cleaned = _strip_or_none(value)
    if cleaned is None:
        return None
    return normalize_github_username(cleaned)


def parse_linkedin_username(value: str | None) -> str | None:
    cleaned = _strip_or_none(value)
    if cleaned is None:
        return None
    return normalize_linkedin_username(cleaned)


def parse_twitter_username(value: str | None) -> str | None:
    cleaned = _strip_or_none(value)
    if cleaned is None:
        return None
    return normalize_twitter_username(cleaned)


def parse_website(value: str | None) -> str | None:
    cleaned = _strip_or_none(value)
    if cleaned is None:
        return None
    return normalize_website(cleaned)

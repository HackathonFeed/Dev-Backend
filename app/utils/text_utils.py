from urllib.parse import urlparse, urlunparse


def normalize_search_query(query: str | None) -> str | None:
    if query is None:
        return None
    cleaned = " ".join(query.strip().split())
    return cleaned or None


def normalize_hackathon_url(url: str | None) -> str:
    """Fix scraper bugs such as duplicated base URLs in stored hackathon links."""
    if not url:
        return ""

    cleaned = url.strip()
    if not cleaned:
        return ""

    for scheme in ("https://", "http://"):
        second = cleaned.find(scheme, len(scheme))
        if second > 0:
            cleaned = cleaned[second:]
            break

    parsed = urlparse(cleaned)
    if parsed.scheme and parsed.netloc:
        path = parsed.path.replace("//", "/")
        cleaned = urlunparse(
            (parsed.scheme, parsed.netloc, path, parsed.params, parsed.query, parsed.fragment)
        )

    return cleaned

def normalize_search_query(query: str | None) -> str | None:
    if query is None:
        return None
    cleaned = " ".join(query.strip().split())
    return cleaned or None

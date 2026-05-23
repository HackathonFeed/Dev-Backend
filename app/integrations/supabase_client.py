from functools import lru_cache

from supabase import Client, create_client

from app.core.config import get_settings


@lru_cache
def get_supabase_client() -> Client | None:
    settings = get_settings()
    if not settings.supabase_url or not settings.effective_supabase_key:
        return None
    return create_client(settings.supabase_url, settings.effective_supabase_key)


def is_supabase_configured() -> bool:
    return get_supabase_client() is not None

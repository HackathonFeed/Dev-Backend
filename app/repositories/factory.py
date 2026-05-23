import asyncio
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.integrations.supabase_client import is_supabase_configured
from app.repositories.analytics_repository import AnalyticsRepository
from app.repositories.bookmark_repository import BookmarkRepository
from app.repositories.supabase_bookmark_repository import SupabaseBookmarkRepository
from app.repositories.supabase_user_repository import SupabaseUserRepository
from app.repositories.user_repository import UserRepository


def get_hackathon_repository(session: AsyncSession | None = None):
    settings = get_settings()
    if settings.use_supabase_data_layer and is_supabase_configured():
        from app.repositories.supabase_hackathon_repository import SupabaseHackathonRepository

        return SupabaseHackathonRepository()
    if session is None:
        raise RuntimeError("Database session required when Supabase data layer is disabled")
    from app.repositories.hackathon_repository import HackathonRepository

    return HackathonRepository(session)


def get_user_repository(session: AsyncSession):
    settings = get_settings()
    if settings.use_supabase_data_layer and is_supabase_configured():
        return SupabaseUserRepository()
    return UserRepository(session)


def get_bookmark_repository(session: AsyncSession):
    settings = get_settings()
    if settings.use_supabase_data_layer and is_supabase_configured():
        return SupabaseBookmarkRepository()
    return BookmarkRepository(session)


class SupabaseAnalyticsRepository:
    """Best-effort analytics logging via Supabase REST."""

    TABLE_EVENTS = "analytics_events"
    TABLE_SEARCH = "search_logs"

    def __init__(self):
        from app.integrations.supabase_client import get_supabase_client

        self.client = get_supabase_client()
        if self.client is None:
            raise RuntimeError("Supabase is not configured")

    async def log_event(
        self,
        *,
        event_type: str,
        entity_type: str | None = None,
        entity_id: str | None = None,
        user_id: uuid.UUID | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        def _insert():
            self.client.table(self.TABLE_EVENTS).insert(
                {
                    "event_type": event_type,
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                    "user_id": str(user_id) if user_id else None,
                    "metadata": metadata,
                }
            ).execute()

        await asyncio.to_thread(_insert)

    async def log_search(
        self,
        *,
        query: str | None,
        filters: dict[str, Any] | None,
        result_count: int,
        user_id: uuid.UUID | None = None,
    ):
        def _insert():
            self.client.table(self.TABLE_SEARCH).insert(
                {
                    "query": query,
                    "filters": filters,
                    "result_count": result_count,
                    "user_id": str(user_id) if user_id else None,
                }
            ).execute()

        await asyncio.to_thread(_insert)

    async def get_event_counts(self) -> dict[str, int]:
        return {}

    async def get_search_count(self) -> int:
        return 0


def get_analytics_repository(session: AsyncSession):
    settings = get_settings()
    if settings.use_supabase_data_layer and is_supabase_configured():
        return SupabaseAnalyticsRepository()
    return AnalyticsRepository(session)

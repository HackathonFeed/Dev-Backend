import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analytics_model import AnalyticsEvent, SearchLog


class AnalyticsRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def log_event(
        self,
        *,
        event_type: str,
        entity_type: str | None = None,
        entity_id: str | None = None,
        user_id: uuid.UUID | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AnalyticsEvent:
        event = AnalyticsEvent(
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            user_id=user_id,
            event_metadata=metadata,
        )
        self.session.add(event)
        await self.session.flush()
        return event

    async def log_search(
        self,
        *,
        query: str | None,
        filters: dict[str, Any] | None,
        result_count: int,
        user_id: uuid.UUID | None = None,
    ) -> SearchLog:
        log = SearchLog(
            query=query,
            filters=filters,
            result_count=result_count,
            user_id=user_id,
        )
        self.session.add(log)
        await self.session.flush()
        return log

    async def get_event_counts(self) -> dict[str, int]:
        result = await self.session.execute(
            select(AnalyticsEvent.event_type, func.count())
            .group_by(AnalyticsEvent.event_type)
        )
        return {event_type: count for event_type, count in result.all()}

    async def get_search_count(self) -> int:
        result = await self.session.execute(select(func.count()).select_from(SearchLog))
        return result.scalar_one()

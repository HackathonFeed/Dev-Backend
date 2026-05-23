import uuid
from math import ceil

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.factory import get_analytics_repository, get_hackathon_repository
from app.schemas.hackathon_schema import HackathonFilterParams, HackathonResponse, PlatformCount, ThemeCount
from app.schemas.response_schema import PaginatedData
from app.utils.text_utils import normalize_search_query


class HackathonService:
    def __init__(self, session: AsyncSession):
        self.hackathons = get_hackathon_repository(session)
        self.analytics = get_analytics_repository(session)

    async def _safe_log_search(self, **kwargs) -> None:
        try:
            await self.analytics.log_search(**kwargs)
        except Exception:
            if hasattr(self.analytics, "session"):
                await self.analytics.session.rollback()

    async def _safe_log_event(self, **kwargs) -> None:
        try:
            await self.analytics.log_event(**kwargs)
        except Exception:
            if hasattr(self.analytics, "session"):
                await self.analytics.session.rollback()

    async def get_all(self, filters: HackathonFilterParams) -> PaginatedData[HackathonResponse]:
        search = normalize_search_query(filters.search)
        items, total = await self.hackathons.list_hackathons(
            page=filters.page,
            page_size=filters.page_size,
            search=search,
            platform=filters.platform,
            mode=filters.mode.value if filters.mode else None,
            theme=filters.theme,
            sort=filters.sort,
            only_open=filters.only_open,
            status=filters.status.value if filters.status else None,
        )

        if search or filters.platform or filters.mode or filters.theme:
            await self._safe_log_search(
                query=search,
                filters={
                    "platform": filters.platform,
                    "mode": filters.mode.value if filters.mode else None,
                    "theme": filters.theme,
                    "sort": filters.sort.value,
                },
                result_count=total,
            )

        pages = max(1, ceil(total / filters.page_size)) if total else 0
        return PaginatedData(
            items=[HackathonResponse.model_validate(item) for item in items],
            total=total,
            page=filters.page,
            page_size=filters.page_size,
            pages=pages,
        )

    async def get_by_id(self, hackathon_id: uuid.UUID) -> HackathonResponse:
        hackathon = await self.hackathons.get_by_id(hackathon_id)
        if not hackathon:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Hackathon not found",
            )

        await self._safe_log_event(
            event_type="hackathon_view",
            entity_type="hackathon",
            entity_id=str(hackathon_id),
        )
        return HackathonResponse.model_validate(hackathon)

    async def get_trending(self, limit: int = 10) -> list[HackathonResponse]:
        items = await self.hackathons.get_trending(limit=limit)
        return [HackathonResponse.model_validate(item) for item in items]

    async def get_themes(self, limit: int = 30) -> list[ThemeCount]:
        rows = await self.hackathons.get_themes(limit=limit)
        return [ThemeCount(theme=theme, count=count) for theme, count in rows]

    async def get_platforms(self) -> list[PlatformCount]:
        rows = await self.hackathons.get_platforms()
        return [
            PlatformCount(platform=platform, total_count=total, open_count=open_count)
            for platform, total, open_count in rows
        ]

    async def delete_hackathon(self, hackathon_id: uuid.UUID) -> None:
        deleted = await self.hackathons.delete_by_id(hackathon_id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Hackathon not found",
            )

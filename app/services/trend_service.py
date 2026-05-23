from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.factory import get_analytics_repository, get_hackathon_repository
from app.schemas.hackathon_schema import HackathonResponse
from app.services.hackathon_service import HackathonService


class TrendService:
    def __init__(self, session: AsyncSession):
        self.hackathons = get_hackathon_repository(session)
        self.analytics = get_analytics_repository(session)
        self.hackathon_service = HackathonService(session)

    async def get_trending_hackathons(self, limit: int = 10) -> list[HackathonResponse]:
        return await self.hackathon_service.get_trending(limit=limit)

    async def get_popular_themes(self, limit: int = 10) -> list[dict]:
        themes = await self.hackathon_service.get_themes(limit=limit)
        return [theme.model_dump() for theme in themes]

    async def get_platform_overview(self) -> list[dict]:
        platforms = await self.hackathon_service.get_platforms()
        return [platform.model_dump() for platform in platforms]

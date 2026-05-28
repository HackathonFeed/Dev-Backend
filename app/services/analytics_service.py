from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.factory import get_analytics_repository, get_hackathon_repository


class AnalyticsService:
    def __init__(self, session: AsyncSession):
        self.analytics = get_analytics_repository(session)
        self.hackathons = get_hackathon_repository(session)

    async def get_dashboard_stats(self) -> dict:
        total_hackathons = await self.hackathons.count_all()
        try:
            event_counts = await self.analytics.get_event_counts()
            search_count = await self.analytics.get_search_count()
        except Exception:
            if hasattr(self.analytics, "session"):
                await self.analytics.session.rollback()
            event_counts = {}
            search_count = 0

        return {
            "total_hackathons": total_hackathons,
            "total_searches": search_count,
            "events": event_counts,
        }

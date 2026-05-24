import uuid
from datetime import date

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import HackathonSort
from app.models.hackathon_model import Hackathon
from app.utils.date_utils import utc_today
from app.utils.hackathon_status_utils import apply_status_date_filters


class HackathonRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    def _apply_filters(
        self,
        query,
        *,
        search: str | None = None,
        platform: str | None = None,
        mode: str | None = None,
        theme: str | None = None,
        only_open: bool = True,
        status: str | None = None,
    ):
        if status:
            query = apply_status_date_filters(query, only_open=False, status=status)
        elif only_open:
            query = apply_status_date_filters(query, only_open=True)

        if platform:
            query = query.where(Hackathon.source_platform == platform.lower())

        if mode:
            query = query.where(Hackathon.mode == mode.lower())

        if theme:
            query = query.where(Hackathon.categories.contains([theme]))

        if search:
            pattern = f"%{search}%"
            query = query.where(
                or_(
                    Hackathon.title.ilike(pattern),
                    Hackathon.organizer.ilike(pattern),
                    Hackathon.tags.any(search),
                    Hackathon.categories.any(search),
                )
            )

        return query

    def _apply_sort(self, query, sort: HackathonSort):
        if sort == HackathonSort.REGISTRATIONS:
            return query.order_by(Hackathon.registrations.desc().nullslast())
        if sort == HackathonSort.SCRAPED_AT:
            return query.order_by(Hackathon.scraped_at.desc().nullslast())
        if sort == HackathonSort.START_DATE:
            return query.order_by(Hackathon.start_date.asc().nullslast())
        return query.order_by(Hackathon.deadline.asc().nullslast())

    async def get_by_id(self, hackathon_id: uuid.UUID) -> Hackathon | None:
        result = await self.session.execute(
            select(Hackathon).where(Hackathon.id == hackathon_id)
        )
        return result.scalar_one_or_none()

    async def list_hackathons(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        search: str | None = None,
        platform: str | None = None,
        mode: str | None = None,
        theme: str | None = None,
        sort: HackathonSort = HackathonSort.DEADLINE,
        only_open: bool = True,
        status: str | None = None,
    ) -> tuple[list[Hackathon], int]:
        base_query = select(Hackathon)
        filtered_query = self._apply_filters(
            base_query,
            search=search,
            platform=platform,
            mode=mode,
            theme=theme,
            only_open=only_open,
            status=status,
        )

        count_query = select(func.count()).select_from(filtered_query.subquery())
        total = (await self.session.execute(count_query)).scalar_one()

        offset = (page - 1) * page_size
        items_query = self._apply_sort(filtered_query, sort).offset(offset).limit(page_size)
        result = await self.session.execute(items_query)
        return list(result.scalars().all()), total

    async def get_trending(self, limit: int = 10) -> list[Hackathon]:
        today = utc_today()
        query = apply_status_date_filters(select(Hackathon), only_open=True, today=today)
        query = (
            query.order_by(Hackathon.registrations.desc().nullslast(), Hackathon.deadline.asc().nullslast())
            .limit(limit)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_themes(self, limit: int = 30) -> list[tuple[str, int]]:
        query = (
            select(
                func.unnest(Hackathon.categories).label("theme"),
                func.count().label("count"),
            )
            .group_by("theme")
            .order_by(func.count().desc())
            .limit(limit)
        )
        result = await self.session.execute(query)
        return [(row.theme, row.count) for row in result.all() if row.theme]

    async def get_platforms(self) -> list[tuple[str, int, int]]:
        today: date = utc_today()
        query = (
            select(
                Hackathon.source_platform.label("platform"),
                func.count().label("total_count"),
                func.count()
                .filter(
                    and_(
                        or_(Hackathon.deadline.is_(None), Hackathon.deadline >= today),
                        or_(Hackathon.end_date.is_(None), Hackathon.end_date >= today),
                    )
                )
                .label("open_count"),
            )
            .group_by(Hackathon.source_platform)
            .order_by(func.count().desc())
        )
        result = await self.session.execute(query)
        return [(row.platform, row.total_count, row.open_count) for row in result.all()]

    async def delete_by_id(self, hackathon_id: uuid.UUID) -> bool:
        hackathon = await self.get_by_id(hackathon_id)
        if not hackathon:
            return False
        await self.session.delete(hackathon)
        await self.session.flush()
        return True

    async def count_all(self) -> int:
        result = await self.session.execute(select(func.count()).select_from(Hackathon))
        return result.scalar_one()

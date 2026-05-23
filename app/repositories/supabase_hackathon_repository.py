import asyncio
import uuid
from collections import Counter
from datetime import date, datetime

from app.core.constants import EventMode, HackathonSort, RegistrationStatus
from app.integrations.supabase_client import get_supabase_client
from app.models.hackathon_model import Hackathon
from app.utils.date_utils import utc_today


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value)


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _row_to_hackathon(row: dict) -> Hackathon:
    mode = row.get("mode") or EventMode.UNKNOWN.value
    status = row.get("status")
    return Hackathon(
        id=uuid.UUID(row["id"]),
        title=row["title"],
        platform_id=row.get("platform_id"),
        organizer=row.get("organizer") or "Unknown",
        url=row["url"],
        thumbnail=row.get("thumbnail"),
        start_date=_parse_date(row.get("start_date")),
        end_date=_parse_date(row.get("end_date")),
        deadline=_parse_date(row.get("deadline")),
        prize_pool=row.get("prize_pool") or "Not specified",
        mode=EventMode(mode) if mode in EventMode._value2member_map_ else EventMode.UNKNOWN,
        location=row.get("location"),
        status=RegistrationStatus(status) if status in RegistrationStatus._value2member_map_ else None,
        registrations=row.get("registrations"),
        eligibility=row.get("eligibility") or [],
        team_size=row.get("team_size") or "Not specified",
        categories=row.get("categories") or [],
        tags=row.get("tags") or [],
        sponsors=row.get("sponsors") or [],
        source_platform=row["source_platform"],
        scraped_at=_parse_datetime(row.get("scraped_at")),
        created_at=_parse_datetime(row.get("created_at")),
        updated_at=_parse_datetime(row.get("updated_at")),
    )


class SupabaseHackathonRepository:
    """Read hackathons via Supabase REST/RPC using the service role key."""

    def __init__(self):
        self.client = get_supabase_client()
        if self.client is None:
            raise RuntimeError("Supabase is not configured")

    async def get_by_id(self, hackathon_id: uuid.UUID) -> Hackathon | None:
        def _fetch():
            response = (
                self.client.table("hackathons")
                .select("*")
                .eq("id", str(hackathon_id))
                .limit(1)
                .execute()
            )
            if not response.data:
                return None
            return _row_to_hackathon(response.data[0])

        return await asyncio.to_thread(_fetch)

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
        offset = (page - 1) * page_size

        if search or platform or mode:
            def _search_rpc():
                response = self.client.rpc(
                    "search_hackathons",
                    {
                        "p_query": search,
                        "p_platform": platform.lower() if platform else None,
                        "p_mode": mode.lower() if mode else None,
                        "p_limit": page_size,
                        "p_offset": offset,
                    },
                ).execute()
                rows = response.data or []
                return [_row_to_hackathon(row) for row in rows], len(rows)

            return await asyncio.to_thread(_search_rpc)

        def _fetch():
            query = self.client.table("hackathons").select("*", count="exact")
            if status:
                query = query.eq("status", status)
            elif only_open:
                today = utc_today().isoformat()
                query = query.or_(f"deadline.is.null,deadline.gte.{today}")
            if platform:
                query = query.eq("source_platform", platform.lower())
            if mode:
                query = query.eq("mode", mode.lower())
            if theme:
                query = query.contains("categories", [theme])
            if sort == HackathonSort.REGISTRATIONS:
                query = query.order("registrations", desc=True)
            elif sort == HackathonSort.SCRAPED_AT:
                query = query.order("scraped_at", desc=True)
            elif sort == HackathonSort.START_DATE:
                query = query.order("start_date", desc=False)
            else:
                query = query.order("deadline", desc=False)
            response = query.range(offset, offset + page_size - 1).execute()
            rows = response.data or []
            total = response.count or len(rows)
            return [_row_to_hackathon(row) for row in rows], total

        return await asyncio.to_thread(_fetch)

    async def get_trending(self, limit: int = 10) -> list[Hackathon]:
        def _fetch():
            today = utc_today().isoformat()
            response = (
                self.client.table("hackathons")
                .select("*")
                .or_(f"deadline.is.null,deadline.gte.{today}")
                .order("registrations", desc=True)
                .order("deadline", desc=False)
                .limit(limit)
                .execute()
            )
            return [_row_to_hackathon(row) for row in (response.data or [])]

        return await asyncio.to_thread(_fetch)

    async def get_themes(self, limit: int = 30) -> list[tuple[str, int]]:
        def _fetch():
            response = self.client.table("hackathons").select("categories").execute()
            counter: Counter[str] = Counter()
            for row in response.data or []:
                for category in row.get("categories") or []:
                    if category:
                        counter[category.strip()] += 1
            return counter.most_common(limit)

        return await asyncio.to_thread(_fetch)

    async def get_platforms(self) -> list[tuple[str, int, int]]:
        def _fetch():
            response = self.client.rpc("get_platform_stats", {}).execute()
            rows = response.data or []
            return [
                (row["platform"], row["total_count"], row["open_count"])
                for row in rows
            ]

        return await asyncio.to_thread(_fetch)

    async def delete_by_id(self, hackathon_id: uuid.UUID) -> bool:
        def _delete():
            response = (
                self.client.table("hackathons")
                .delete()
                .eq("id", str(hackathon_id))
                .execute()
            )
            return bool(response.data)

        return await asyncio.to_thread(_delete)

    async def count_all(self) -> int:
        def _fetch():
            response = self.client.table("hackathons").select("*", count="exact").limit(1).execute()
            return response.count or 0

        return await asyncio.to_thread(_fetch)

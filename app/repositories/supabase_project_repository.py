import asyncio
from collections import Counter
from datetime import datetime

from app.integrations.supabase_client import get_supabase_client
from app.schemas.project_schema import (
    ProjectDescriptionSectionResponse,
    ProjectMemberResponse,
    ProjectResponse,
)


def _parse_members(raw: list | None) -> list[ProjectMemberResponse]:
    if not raw:
        return []
    result = []
    for m in raw:
        if isinstance(m, dict):
            result.append(
                ProjectMemberResponse(
                    username=m.get("username", ""),
                    full_name=m.get("full_name"),
                    profile_image=m.get("profile_image"),
                )
            )
    return result


def _parse_sections(raw: list | None) -> list[ProjectDescriptionSectionResponse]:
    if not raw:
        return []
    result = []
    for s in raw:
        if isinstance(s, dict) and s.get("title"):
            result.append(
                ProjectDescriptionSectionResponse(
                    title=s["title"],
                    content=s.get("content", ""),
                )
            )
    return result


def _row_to_project(row: dict) -> ProjectResponse:
    return ProjectResponse(
        id=str(row["id"]),
        title=row.get("title", ""),
        tagline=row.get("tagline"),
        url=row.get("url", ""),
        thumbnail=row.get("thumbnail"),
        description=row.get("description"),
        description_sections=_parse_sections(row.get("description_sections")),
        hackathon_name=row.get("hackathon_name"),
        hackathon_url=row.get("hackathon_url"),
        team_members=_parse_members(row.get("team_members")),
        technologies=row.get("technologies") or [],
        tags=row.get("tags") or [],
        platforms=row.get("platforms") or [],
        likes_count=row.get("likes_count"),
        views=row.get("views"),
        github_url=row.get("github_url"),
        demo_url=row.get("demo_url"),
        prize=row.get("prize"),
        prize_description=row.get("prize_description"),
        is_winner=bool(row.get("is_winner", False)),
        source_platform=row.get("source_platform", "devfolio"),
        scraped_at=row.get("scraped_at"),
    )


class SupabaseProjectRepository:
    """Read devfolio_projects via Supabase REST using the service role key."""

    TABLE = "devfolio_projects"

    def __init__(self):
        self.client = get_supabase_client()
        if self.client is None:
            raise RuntimeError("Supabase is not configured")

    # ── Single project ────────────────────────────────────────────────────────

    async def get_by_id(self, project_id: str) -> ProjectResponse | None:
        def _fetch():
            response = (
                self.client.table(self.TABLE)
                .select("*")
                .eq("id", project_id)
                .limit(1)
                .execute()
            )
            if not response.data:
                return None
            return _row_to_project(response.data[0])

        return await asyncio.to_thread(_fetch)

    # ── Paginated list ────────────────────────────────────────────────────────

    async def list_projects(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        search: str | None = None,
        platform: str | None = None,
        technology: str | None = None,
        is_winner: bool | None = None,
        sort: str = "likes",
    ) -> tuple[list[ProjectResponse], int]:
        offset = (page - 1) * page_size

        def _fetch():
            query = self.client.table(self.TABLE).select("*", count="exact")

            if search:
                escaped = search.replace("%", "\\%")
                query = query.or_(f"title.ilike.%{escaped}%,tagline.ilike.%{escaped}%")

            if platform:
                query = query.contains("platforms", [platform])

            if technology:
                query = query.contains("technologies", [technology])

            if is_winner is True:
                query = query.eq("is_winner", True)

            if sort == "views":
                query = query.order("views", desc=True, nullsfirst=False)
            elif sort == "recent":
                query = query.order("scraped_at", desc=True)
            else:
                # default: likes
                query = query.order("likes_count", desc=True, nullsfirst=False)

            response = query.range(offset, offset + page_size - 1).execute()
            rows = response.data or []
            total = response.count or len(rows)
            return [_row_to_project(row) for row in rows], total

        return await asyncio.to_thread(_fetch)

    # ── Semantic search ───────────────────────────────────────────────────────

    async def semantic_search(
        self,
        embedding: list[float],
        limit: int = 5,
        technology: str | None = None,
        is_winner: bool = False,
    ) -> list[ProjectResponse]:
        """
        Cosine-similarity search using pgvector.
        Calls the `match_projects` SQL function created by the migration.
        """
        def _fetch():
            response = (
                self.client.rpc(
                    "match_projects",
                    {
                        "query_embedding": embedding,
                        "match_count": limit,
                        "filter_winner": is_winner,
                        "filter_technology": technology,
                    },
                )
                .execute()
            )
            return [_row_to_project(row) for row in (response.data or [])]

        return await asyncio.to_thread(_fetch)

    # ── Facets ────────────────────────────────────────────────────────────────

    async def get_platform_stats(self) -> list[tuple[str, int]]:
        """Return (platform, count) sorted descending by count."""

        def _fetch():
            response = self.client.table(self.TABLE).select("platforms").execute()
            counter: Counter[str] = Counter()
            for row in response.data or []:
                for p in row.get("platforms") or []:
                    if p:
                        counter[p.strip()] += 1
            return counter.most_common()

        return await asyncio.to_thread(_fetch)

    async def get_technology_stats(self, limit: int = 40) -> list[tuple[str, int]]:
        """Return (technology, count) sorted descending by count."""

        def _fetch():
            response = self.client.table(self.TABLE).select("technologies").execute()
            counter: Counter[str] = Counter()
            for row in response.data or []:
                for t in row.get("technologies") or []:
                    if t:
                        counter[t.strip()] += 1
            return counter.most_common(limit)

        return await asyncio.to_thread(_fetch)

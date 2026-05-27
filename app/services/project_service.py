from math import ceil

from fastapi import HTTPException, status

from app.repositories.supabase_project_repository import SupabaseProjectRepository
from app.schemas.project_schema import (
    ProjectFilterParams,
    ProjectPlatformStats,
    ProjectResponse,
    ProjectTechnologyStats,
)
from app.schemas.response_schema import PaginatedData


class ProjectService:
    def __init__(self):
        self.repo = SupabaseProjectRepository()

    async def get_all(self, filters: ProjectFilterParams) -> PaginatedData[ProjectResponse]:
        items, total = await self.repo.list_projects(
            page=filters.page,
            page_size=filters.page_size,
            search=filters.search,
            platform=filters.platform,
            technology=filters.technology,
            is_winner=filters.is_winner,
            sort=filters.sort,
        )
        pages = max(1, ceil(total / filters.page_size)) if total else 0
        return PaginatedData(
            items=items,
            total=total,
            page=filters.page,
            page_size=filters.page_size,
            pages=pages,
        )

    async def get_by_id(self, project_id: str) -> ProjectResponse:
        project = await self.repo.get_by_id(project_id)
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found",
            )
        return project

    async def get_platform_stats(self) -> list[ProjectPlatformStats]:
        rows = await self.repo.get_platform_stats()
        return [ProjectPlatformStats(platform=p, count=c) for p, c in rows]

    async def get_technology_stats(self, limit: int = 40) -> list[ProjectTechnologyStats]:
        rows = await self.repo.get_technology_stats(limit=limit)
        return [ProjectTechnologyStats(technology=t, count=c) for t, c in rows]

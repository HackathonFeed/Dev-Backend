from fastapi import APIRouter, Query

from app.schemas.project_schema import (
    ProjectFilterParams,
    ProjectPlatformStats,
    ProjectResponse,
    ProjectTechnologyStats,
)
from app.schemas.response_schema import APIResponse, PaginatedData
from app.services.project_service import ProjectService

router = APIRouter(prefix="/projects", tags=["Projects"])


@router.get("/platforms", response_model=APIResponse[list[ProjectPlatformStats]])
async def list_project_platforms():
    """Return distinct platforms with project counts."""
    service = ProjectService()
    data = await service.get_platform_stats()
    return APIResponse(
        success=True,
        message="Project platforms fetched successfully",
        data=data,
    )


@router.get("/technologies", response_model=APIResponse[list[ProjectTechnologyStats]])
async def list_project_technologies(
    limit: int = Query(default=40, ge=1, le=200),
):
    """Return top technology tags with usage counts."""
    service = ProjectService()
    data = await service.get_technology_stats(limit=limit)
    return APIResponse(
        success=True,
        message="Project technologies fetched successfully",
        data=data,
    )


@router.get("", response_model=APIResponse[PaginatedData[ProjectResponse]])
async def list_projects(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: str | None = None,
    platform: str | None = None,
    technology: str | None = None,
    is_winner: bool | None = None,
    sort: str = Query(default="likes", pattern="^(likes|views|recent)$"),
):
    """List Devfolio projects with filtering and pagination."""
    service = ProjectService()
    filters = ProjectFilterParams(
        page=page,
        page_size=page_size,
        search=search,
        platform=platform,
        technology=technology,
        is_winner=is_winner,
        sort=sort,
    )
    data = await service.get_all(filters)
    return APIResponse(
        success=True,
        message="Projects fetched successfully",
        data=data,
    )


@router.get("/{project_id}", response_model=APIResponse[ProjectResponse])
async def get_project(project_id: str):
    """Fetch a single project by its UUID."""
    service = ProjectService()
    data = await service.get_by_id(project_id)
    return APIResponse(
        success=True,
        message="Project fetched successfully",
        data=data,
    )

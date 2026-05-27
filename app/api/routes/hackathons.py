import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import HackathonSort
from app.core.database import get_db
from app.schemas.hackathon_schema import HackathonFilterParams, HackathonResponse
from app.schemas.response_schema import APIResponse, PaginatedData
from app.services.hackathon_service import HackathonService

router = APIRouter(prefix="/hackathons", tags=["Hackathons"])


@router.get("", response_model=APIResponse[PaginatedData[HackathonResponse]])
async def list_hackathons(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    theme: str | None = None,
    mode: str | None = None,
    platform: str | None = None,
    search: str | None = None,
    sort: HackathonSort = HackathonSort.DEADLINE,
    only_open: bool = True,
    status: str | None = None,
    session: AsyncSession = Depends(get_db),
):
    service = HackathonService(session)
    filters = HackathonFilterParams(
        page=page,
        page_size=page_size,
        theme=theme,
        mode=mode,
        platform=platform,
        search=search,
        sort=sort,
        only_open=only_open,
        status=status,
    )
    data = await service.get_all(filters)
    return APIResponse(
        success=True,
        message="Hackathons fetched successfully",
        data=data,
    )


@router.get("/search", response_model=APIResponse[PaginatedData[HackathonResponse]])
async def search_hackathons(
    search: str = Query(..., min_length=1),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    theme: str | None = None,
    mode: str | None = None,
    platform: str | None = None,
    sort: HackathonSort = HackathonSort.DEADLINE,
    only_open: bool = True,
    status: str | None = None,
    session: AsyncSession = Depends(get_db),
):
    service = HackathonService(session)
    filters = HackathonFilterParams(
        page=page,
        page_size=page_size,
        theme=theme,
        mode=mode,
        platform=platform,
        search=search,
        sort=sort,
        only_open=only_open,
        status=status,
    )
    data = await service.get_all(filters)
    return APIResponse(
        success=True,
        message="Search completed successfully",
        data=data,
    )


@router.get("/trending", response_model=APIResponse[list[HackathonResponse]])
async def get_trending_hackathons(
    limit: int = Query(default=10, ge=1, le=50),
    session: AsyncSession = Depends(get_db),
):
    service = HackathonService(session)
    data = await service.get_trending(limit=limit)
    return APIResponse(
        success=True,
        message="Trending hackathons fetched successfully",
        data=data,
    )


@router.get("/{hackathon_id}", response_model=APIResponse[HackathonResponse])
async def get_hackathon(
    hackathon_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
):
    service = HackathonService(session)
    data = await service.get_by_id(hackathon_id)
    return APIResponse(
        success=True,
        message="Hackathon fetched successfully",
        data=data,
    )

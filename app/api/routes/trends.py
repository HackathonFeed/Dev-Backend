from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.response_schema import APIResponse
from app.services.trend_service import TrendService

router = APIRouter(prefix="/trends", tags=["Trends"])


@router.get("/hackathons", response_model=APIResponse[list])
async def trending_hackathons(
    limit: int = Query(default=10, ge=1, le=50),
    session: AsyncSession = Depends(get_db),
):
    service = TrendService(session)
    data = await service.get_trending_hackathons(limit=limit)
    return APIResponse(
        success=True,
        message="Trending hackathons fetched successfully",
        data=[item.model_dump() for item in data],
    )


@router.get("/themes", response_model=APIResponse[list])
async def trending_themes(
    limit: int = Query(default=10, ge=1, le=50),
    session: AsyncSession = Depends(get_db),
):
    service = TrendService(session)
    data = await service.get_popular_themes(limit=limit)
    return APIResponse(
        success=True,
        message="Popular themes fetched successfully",
        data=data,
    )


@router.get("/platforms", response_model=APIResponse[list])
async def platform_overview(session: AsyncSession = Depends(get_db)):
    service = TrendService(session)
    data = await service.get_platform_overview()
    return APIResponse(
        success=True,
        message="Platform overview fetched successfully",
        data=data,
    )

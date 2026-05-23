import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth_dependency import require_admin
from app.core.database import get_db
from app.schemas.response_schema import APIResponse
from app.services.analytics_service import AnalyticsService
from app.services.hackathon_service import HackathonService

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/stats", response_model=APIResponse[dict])
async def get_admin_stats(
    _: object = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    service = AnalyticsService(session)
    data = await service.get_dashboard_stats()
    return APIResponse(
        success=True,
        message="Admin stats fetched successfully",
        data=data,
    )


@router.post("/scrape", response_model=APIResponse[dict])
async def trigger_scrape(
    _: object = Depends(require_admin),
):
    return APIResponse(
        success=True,
        message="Scrape trigger acknowledged. Connect this endpoint to the scraper scheduler.",
        data={"status": "queued"},
    )


@router.delete("/hackathon/{hackathon_id}", response_model=APIResponse[None])
async def delete_hackathon(
    hackathon_id: uuid.UUID,
    _: object = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    service = HackathonService(session)
    await service.delete_hackathon(hackathon_id)
    return APIResponse(
        success=True,
        message="Hackathon deleted successfully",
        data=None,
    )

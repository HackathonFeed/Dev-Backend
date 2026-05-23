from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.hackathon_schema import PlatformCount
from app.schemas.response_schema import APIResponse
from app.services.hackathon_service import HackathonService

router = APIRouter(tags=["Platforms"])


@router.get("/platforms", response_model=APIResponse[list[PlatformCount]])
async def list_platforms(session: AsyncSession = Depends(get_db)):
    service = HackathonService(session)
    data = await service.get_platforms()
    return APIResponse(
        success=True,
        message="Platforms fetched successfully",
        data=data,
    )

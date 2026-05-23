from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.hackathon_schema import ThemeCount
from app.schemas.response_schema import APIResponse
from app.services.hackathon_service import HackathonService

router = APIRouter(prefix="/themes", tags=["Themes"])


@router.get("", response_model=APIResponse[list[ThemeCount]])
async def list_themes(
    limit: int = Query(default=30, ge=1, le=100),
    session: AsyncSession = Depends(get_db),
):
    service = HackathonService(session)
    data = await service.get_themes(limit=limit)
    return APIResponse(
        success=True,
        message="Themes fetched successfully",
        data=data,
    )

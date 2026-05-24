import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth_dependency import get_current_user
from app.core.database import get_db
from app.schemas.bookmark_schema import BookmarkResponse
from app.schemas.response_schema import APIResponse
from app.services.bookmark_service import BookmarkService
from app.utils.bookmark_mapper import to_bookmark_response

router = APIRouter(prefix="/bookmarks", tags=["Bookmarks"])


@router.post("/{hackathon_id}", response_model=APIResponse[BookmarkResponse])
async def create_bookmark(
    hackathon_id: uuid.UUID,
    current_user=Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = BookmarkService(session)
    bookmark = await service.add_bookmark(current_user.id, hackathon_id)
    return APIResponse(
        success=True,
        message="Hackathon bookmarked successfully",
        data=to_bookmark_response(bookmark),
    )


@router.get("", response_model=APIResponse[list[BookmarkResponse]])
async def list_bookmarks(
    current_user=Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = BookmarkService(session)
    bookmarks = await service.list_bookmarks(current_user.id)
    return APIResponse(
        success=True,
        message="Bookmarks fetched successfully",
        data=[to_bookmark_response(item) for item in bookmarks],
    )


@router.delete("/{hackathon_id}", response_model=APIResponse[None])
async def delete_bookmark(
    hackathon_id: uuid.UUID,
    current_user=Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = BookmarkService(session)
    await service.remove_bookmark(current_user.id, hackathon_id)
    return APIResponse(
        success=True,
        message="Bookmark removed successfully",
        data=None,
    )

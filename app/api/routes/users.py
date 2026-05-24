import uuid

from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth_dependency import get_current_user
from app.core.database import get_db
from app.schemas.auth_schema import UserResponse, UserUpdateRequest
from app.schemas.leaderboard_schema import LeaderboardEntryResponse, UserHackathonStatsResponse
from app.schemas.response_schema import APIResponse
from app.services.leaderboard_service import LeaderboardService
from app.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/public/{username}", response_model=APIResponse[UserHackathonStatsResponse])
async def get_public_profile(
    username: str,
    session: AsyncSession = Depends(get_db),
):
    service = LeaderboardService(session)
    stats = await service.get_public_profile_by_username(username)
    return APIResponse(
        success=True,
        message="Public profile fetched successfully",
        data=stats,
    )


@router.get("/leaderboard", response_model=APIResponse[list[LeaderboardEntryResponse]])
async def get_leaderboard(
    limit: int = Query(default=50, ge=1, le=100),
    _current_user=Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = LeaderboardService(session)
    entries = await service.get_leaderboard(limit=limit)
    return APIResponse(
        success=True,
        message="Leaderboard fetched successfully",
        data=entries,
    )


@router.get("/me", response_model=APIResponse[UserResponse])
async def get_profile(
    current_user=Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = UserService(session)
    user = await service.get_profile(current_user.id)
    return APIResponse(
        success=True,
        message="User profile fetched successfully",
        data=UserResponse.model_validate(user),
    )


@router.patch("/me", response_model=APIResponse[UserResponse])
async def update_profile(
    payload: UserUpdateRequest,
    current_user=Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = UserService(session)
    user = await service.update_profile(current_user.id, payload)
    return APIResponse(
        success=True,
        message="Profile updated successfully",
        data=UserResponse.model_validate(user),
    )


@router.post("/me/avatar", response_model=APIResponse[UserResponse])
async def upload_profile_avatar(
    file: UploadFile = File(...),
    current_user=Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = UserService(session)
    user = await service.upload_avatar(current_user.id, file)
    return APIResponse(
        success=True,
        message="Profile photo uploaded successfully",
        data=UserResponse.model_validate(user),
    )


@router.delete("/me/avatar", response_model=APIResponse[UserResponse])
async def remove_profile_avatar(
    current_user=Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = UserService(session)
    user = await service.remove_avatar(current_user.id)
    return APIResponse(
        success=True,
        message="Profile photo removed successfully",
        data=UserResponse.model_validate(user),
    )


@router.get("/{user_id}/hackathon-stats", response_model=APIResponse[UserHackathonStatsResponse])
async def get_user_hackathon_stats(
    user_id: uuid.UUID,
    _current_user=Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = LeaderboardService(session)
    stats = await service.get_user_stats(user_id)
    return APIResponse(
        success=True,
        message="User hackathon stats fetched successfully",
        data=stats,
    )

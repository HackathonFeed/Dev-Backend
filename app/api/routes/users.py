from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth_dependency import get_current_user
from app.core.database import get_db
from app.schemas.auth_schema import UserResponse, UserUpdateRequest
from app.schemas.response_schema import APIResponse
from app.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["Users"])


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

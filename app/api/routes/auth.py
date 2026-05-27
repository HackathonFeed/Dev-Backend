from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth_dependency import get_current_user
from app.core.database import get_db
from app.schemas.auth_schema import (
    GoogleLoginRequest,
    RefreshTokenRequest,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)
from app.schemas.response_schema import APIResponse, TokenPayload
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=APIResponse[TokenPayload])
async def register(
    payload: UserRegisterRequest,
    session: AsyncSession = Depends(get_db),
):
    service = AuthService(session)
    user, access_token, refresh_token = await service.register(payload)
    return APIResponse(
        success=True,
        message="Registration successful",
        data=TokenPayload(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=AuthService.token_expiry_seconds(),
        ),
    )


@router.post("/google", response_model=APIResponse[TokenPayload])
async def google_login(
    payload: GoogleLoginRequest,
    session: AsyncSession = Depends(get_db),
):
    service = AuthService(session)
    _, access_token, refresh_token = await service.login_with_google(
        id_token_value=payload.id_token,
        access_token_value=payload.access_token,
    )
    return APIResponse(
        success=True,
        message="Google sign-in successful",
        data=TokenPayload(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=AuthService.token_expiry_seconds(),
        ),
    )


@router.post("/login", response_model=APIResponse[TokenPayload])
async def login(
    payload: UserLoginRequest,
    session: AsyncSession = Depends(get_db),
):
    service = AuthService(session)
    _, access_token, refresh_token = await service.login(payload)
    return APIResponse(
        success=True,
        message="Login successful",
        data=TokenPayload(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=AuthService.token_expiry_seconds(),
        ),
    )


@router.post("/refresh", response_model=APIResponse[TokenPayload])
async def refresh_token(
    payload: RefreshTokenRequest,
    session: AsyncSession = Depends(get_db),
):
    service = AuthService(session)
    access_token, refresh_token = await service.refresh(payload.refresh_token)
    return APIResponse(
        success=True,
        message="Token refreshed successfully",
        data=TokenPayload(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=AuthService.token_expiry_seconds(),
        ),
    )


@router.get("/me", response_model=APIResponse[UserResponse])
async def get_me(
    current_user=Depends(get_current_user),
):
    return APIResponse(
        success=True,
        message="Profile fetched successfully",
        data=UserResponse.model_validate(current_user),
    )

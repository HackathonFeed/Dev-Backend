from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth_dependency import get_current_user
from app.core.database import get_db
from app.core.security import hash_password
from app.repositories import factory as repository_factory
from app.schemas.auth_schema import (
    ForgotPasswordRequest,
    GoogleLoginRequest,
    RefreshTokenRequest,
    ResetPasswordRequest,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
    VerifyResetCodeRequest,
)
from app.schemas.response_schema import APIResponse, TokenPayload
from app.services.auth_service import AuthService
from app.services.email_service import EmailService
from app.services import password_reset_service as prs

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
    try:
        _, access_token, refresh_token = await service.login_with_google(
            id_token_value=payload.id_token,
            access_token_value=payload.access_token,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Google sign-in could not create a user session: {exc}",
        ) from exc
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


# ── Forgot Password ───────────────────────────────────────────────────────────

@router.post("/forgot-password", response_model=APIResponse[None])
async def forgot_password(
    payload: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    """Send a 6-digit OTP to the user's email. Always returns 200 to avoid user enumeration."""
    repo = repository_factory.get_user_repository(db)
    user = await repo.get_by_email(str(payload.email))
    if user:
        code = prs.generate_and_store_code(str(payload.email))
        await EmailService.send_reset_code(user.email, user.name, code)
    # Always return success so attackers can't enumerate registered emails
    return APIResponse(success=True, message="If that email is registered, a reset code has been sent.", data=None)


@router.post("/verify-reset-code", response_model=APIResponse[dict])
async def verify_reset_code(payload: VerifyResetCodeRequest):
    """Verify the OTP and return a single-use reset_token."""
    token = prs.verify_code_and_issue_token(str(payload.email), payload.code)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired code. Please request a new one.",
        )
    return APIResponse(success=True, message="Code verified.", data={"reset_token": token})


@router.post("/reset-password", response_model=APIResponse[None])
async def reset_password(
    payload: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    """Consume the reset_token and update the user's password."""
    email = prs.consume_reset_token(payload.reset_token)
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token. Please start over.",
        )
    repo = repository_factory.get_user_repository(db)
    user = await repo.get_by_email(email)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    user.password_hash = hash_password(payload.new_password)
    await repo.update(user)
    return APIResponse(success=True, message="Password updated successfully.", data=None)

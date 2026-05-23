import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.constants import UserRole
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
    verify_token,
)
from app.models.user_model import User
from app.repositories.factory import get_user_repository
from app.schemas.auth_schema import UserLoginRequest, UserRegisterRequest, UserUpdateRequest


class AuthService:
    def __init__(self, session: AsyncSession):
        self.users = get_user_repository(session)

    async def register(self, payload: UserRegisterRequest) -> tuple[User, str, str]:
        existing = await self.users.get_by_email(payload.email)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already registered",
            )

        user = User(
            id=uuid.uuid4(),
            name=payload.name.strip(),
            email=payload.email.lower(),
            password_hash=hash_password(payload.password),
            role=UserRole.USER,
        )
        user = await self.users.create(user)
        access_token = create_access_token(str(user.id), user.email, user.role)
        refresh_token = create_refresh_token(str(user.id), user.email, user.role)
        return user, access_token, refresh_token

    async def login(self, payload: UserLoginRequest) -> tuple[User, str, str]:
        user = await self.users.get_by_email(payload.email)
        if not user or not verify_password(payload.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
            )

        access_token = create_access_token(str(user.id), user.email, user.role)
        refresh_token = create_refresh_token(str(user.id), user.email, user.role)
        return user, access_token, refresh_token

    async def refresh(self, refresh_token: str) -> tuple[str, str]:
        payload = verify_token(refresh_token, expected_type="refresh")
        if not payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token",
            )

        user_id = uuid.UUID(payload["sub"])
        user = await self.users.get_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
            )

        access_token = create_access_token(str(user.id), user.email, user.role)
        new_refresh_token = create_refresh_token(str(user.id), user.email, user.role)
        return access_token, new_refresh_token

    async def get_current_user(self, user_id: uuid.UUID) -> User:
        user = await self.users.get_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )
        return user

    async def update_profile(self, user_id: uuid.UUID, payload: UserUpdateRequest) -> User:
        user = await self.users.get_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        if payload.name is not None:
            user.name = payload.name.strip()
        if payload.interests is not None:
            user.interests = [interest.strip() for interest in payload.interests if interest.strip()]

        return await self.users.update(user)

    @staticmethod
    def token_expiry_seconds() -> int:
        return get_settings().access_token_expire_minutes * 60

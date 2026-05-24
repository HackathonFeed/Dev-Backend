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
from app.utils.username_utils import generate_username_candidate, validate_username_or_raise


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

        user_id = uuid.uuid4()
        username = await self._generate_unique_username(payload.name.strip(), user_id)

        user = User(
            id=user_id,
            name=payload.name.strip(),
            username=username,
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
        if payload.username is not None:
            try:
                username = validate_username_or_raise(payload.username)
            except ValueError as exc:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
            if await self.users.username_exists(username, exclude_user_id=user.id):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Username is already taken",
                )
            user.username = username
        if payload.interests is not None:
            user.interests = [interest.strip() for interest in payload.interests if interest.strip()]
        if payload.avatar_url is not None:
            user.avatar_url = payload.avatar_url.strip() or None

        return await self.users.update(user)

    async def _generate_unique_username(self, name: str, user_id: uuid.UUID) -> str:
        for attempt in range(20):
            candidate = generate_username_candidate(name, user_id, attempt)
            if not await self.users.username_exists(candidate):
                return candidate
        fallback = generate_username_candidate(name, user_id, 99)
        if not await self.users.username_exists(fallback):
            return fallback
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not generate a unique username",
        )

    @staticmethod
    def token_expiry_seconds() -> int:
        return get_settings().access_token_expire_minutes * 60

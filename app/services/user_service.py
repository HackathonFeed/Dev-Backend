import uuid

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_model import User
from app.schemas.auth_schema import UserUpdateRequest
from app.services.auth_service import AuthService
from app.services.avatar_service import delete_user_avatar_files, save_user_avatar


class UserService:
    def __init__(self, session: AsyncSession):
        self.auth = AuthService(session)

    async def get_profile(self, user_id: uuid.UUID) -> User:
        return await self.auth.get_current_user(user_id)

    async def update_profile(self, user_id: uuid.UUID, payload: UserUpdateRequest) -> User:
        return await self.auth.update_profile(user_id, payload)

    async def upload_avatar(self, user_id: uuid.UUID, file: UploadFile) -> User:
        user = await self.auth.get_current_user(user_id)
        avatar_url = await save_user_avatar(user.id, file)
        user.avatar_url = avatar_url
        try:
            return await self.auth.users.update(user)
        except Exception as exc:
            message = str(exc).lower()
            if "avatar_url" in message:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=(
                        "Profile photo storage is not set up in Supabase yet. "
                        "Run database/add_user_avatar_url.sql in the Supabase SQL Editor."
                    ),
                ) from exc
            raise

    async def remove_avatar(self, user_id: uuid.UUID) -> User:
        user = await self.auth.get_current_user(user_id)
        delete_user_avatar_files(user.id)
        user.avatar_url = None
        try:
            return await self.auth.users.update(user)
        except Exception as exc:
            message = str(exc).lower()
            if "avatar_url" in message:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=(
                        "Profile photo storage is not set up in Supabase yet. "
                        "Run database/add_user_avatar_url.sql in the Supabase SQL Editor."
                    ),
                ) from exc
            raise
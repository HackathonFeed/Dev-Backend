import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_model import User
from app.schemas.auth_schema import UserUpdateRequest
from app.services.auth_service import AuthService


class UserService:
    def __init__(self, session: AsyncSession):
        self.auth = AuthService(session)

    async def get_profile(self, user_id: uuid.UUID) -> User:
        return await self.auth.get_current_user(user_id)

    async def update_profile(self, user_id: uuid.UUID, payload: UserUpdateRequest) -> User:
        return await self.auth.update_profile(user_id, payload)

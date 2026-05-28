import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_model import User


class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        result = await self.session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        result = await self.session.execute(select(User).where(User.email == email.lower()))
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> User | None:
        result = await self.session.execute(
            select(User).where(User.username == username.lower())
        )
        return result.scalar_one_or_none()

    async def username_exists(self, username: str, *, exclude_user_id: uuid.UUID | None = None) -> bool:
        query = select(User.id).where(User.username == username.lower())
        if exclude_user_id is not None:
            query = query.where(User.id != exclude_user_id)
        result = await self.session.execute(query.limit(1))
        return result.scalar_one_or_none() is not None

    async def create(self, user: User) -> User:
        self.session.add(user)
        await self.session.flush()
        await self.session.refresh(user)
        return user

    async def update(self, user: User) -> User:
        await self.session.flush()
        await self.session.refresh(user)
        return user

    async def deduct_ai_points(self, user_id: uuid.UUID, cost: int) -> User:
        user = await self.get_by_id(user_id)
        if user is None:
            raise RuntimeError("User not found for points deduction")
        if user.ai_points == -1:
            return user
        user.ai_points = max(user.ai_points - cost, 0)
        await self.session.flush()
        await self.session.refresh(user)
        return user

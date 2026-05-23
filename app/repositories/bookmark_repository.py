import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.bookmark_model import Bookmark


class BookmarkRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_user_and_hackathon(
        self, user_id: uuid.UUID, hackathon_id: uuid.UUID
    ) -> Bookmark | None:
        result = await self.session.execute(
            select(Bookmark).where(
                Bookmark.user_id == user_id,
                Bookmark.hackathon_id == hackathon_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_by_user(self, user_id: uuid.UUID) -> list[Bookmark]:
        result = await self.session.execute(
            select(Bookmark)
            .options(selectinload(Bookmark.hackathon))
            .where(Bookmark.user_id == user_id)
            .order_by(Bookmark.created_at.desc())
        )
        return list(result.scalars().all())

    async def create(self, bookmark: Bookmark) -> Bookmark:
        self.session.add(bookmark)
        await self.session.flush()
        await self.session.refresh(bookmark)
        return bookmark

    async def delete(self, bookmark: Bookmark) -> None:
        await self.session.delete(bookmark)
        await self.session.flush()

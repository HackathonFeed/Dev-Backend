import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.bookmark_model import Bookmark
from app.repositories.factory import get_analytics_repository, get_bookmark_repository, get_hackathon_repository


class BookmarkService:
    def __init__(self, session: AsyncSession):
        self.bookmarks = get_bookmark_repository(session)
        self.hackathons = get_hackathon_repository(session)
        self.analytics = get_analytics_repository(session)

    async def add_bookmark(self, user_id: uuid.UUID, hackathon_id: uuid.UUID) -> Bookmark:
        hackathon = await self.hackathons.get_by_id(hackathon_id)
        if not hackathon:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Hackathon not found",
            )

        existing = await self.bookmarks.get_by_user_and_hackathon(user_id, hackathon_id)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Hackathon already bookmarked",
            )

        bookmark = Bookmark(
            id=uuid.uuid4(),
            user_id=user_id,
            hackathon_id=hackathon_id,
        )
        bookmark = await self.bookmarks.create(bookmark)
        await self.analytics.log_event(
            event_type="bookmark_created",
            entity_type="hackathon",
            entity_id=str(hackathon_id),
            user_id=user_id,
        )
        return bookmark

    async def list_bookmarks(self, user_id: uuid.UUID) -> list[Bookmark]:
        return await self.bookmarks.list_by_user(user_id)

    async def remove_bookmark(self, user_id: uuid.UUID, hackathon_id: uuid.UUID) -> None:
        bookmark = await self.bookmarks.get_by_user_and_hackathon(user_id, hackathon_id)
        if not bookmark:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Bookmark not found",
            )

        await self.bookmarks.delete(bookmark)
        await self.analytics.log_event(
            event_type="bookmark_removed",
            entity_type="hackathon",
            entity_id=str(hackathon_id),
            user_id=user_id,
        )

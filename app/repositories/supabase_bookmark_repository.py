import asyncio
import uuid

from app.integrations.supabase_client import get_supabase_client
from app.models.bookmark_model import Bookmark
from app.repositories.supabase_hackathon_repository import _row_to_hackathon


class SupabaseBookmarkRepository:
    TABLE = "bookmarks"

    def __init__(self):
        self.client = get_supabase_client()
        if self.client is None:
            raise RuntimeError("Supabase is not configured")

    async def get_by_user_and_hackathon(
        self, user_id: uuid.UUID, hackathon_id: uuid.UUID
    ) -> Bookmark | None:
        def _fetch():
            response = (
                self.client.table(self.TABLE)
                .select("*, hackathons(*)")
                .eq("user_id", str(user_id))
                .eq("hackathon_id", str(hackathon_id))
                .limit(1)
                .execute()
            )
            if not response.data:
                return None
            return _row_to_bookmark(response.data[0])

        return await asyncio.to_thread(_fetch)

    async def list_by_user(self, user_id: uuid.UUID) -> list[Bookmark]:
        def _fetch():
            response = (
                self.client.table(self.TABLE)
                .select("*, hackathons(*)")
                .eq("user_id", str(user_id))
                .order("created_at", desc=True)
                .execute()
            )
            return [_row_to_bookmark(row) for row in (response.data or [])]

        return await asyncio.to_thread(_fetch)

    async def create(self, bookmark: Bookmark) -> Bookmark:
        def _create():
            payload = {
                "id": str(bookmark.id),
                "user_id": str(bookmark.user_id),
                "hackathon_id": str(bookmark.hackathon_id),
            }
            response = (
                self.client.table(self.TABLE)
                .insert(payload)
                .select("*, hackathons(*)")
                .execute()
            )
            return _row_to_bookmark(response.data[0])

        return await asyncio.to_thread(_create)

    async def delete(self, bookmark: Bookmark) -> None:
        def _delete():
            self.client.table(self.TABLE).delete().eq("id", str(bookmark.id)).execute()

        await asyncio.to_thread(_delete)


def _row_to_bookmark(row: dict) -> Bookmark:
    bookmark = Bookmark(
        id=uuid.UUID(row["id"]),
        user_id=uuid.UUID(row["user_id"]),
        hackathon_id=uuid.UUID(row["hackathon_id"]),
    )
    bookmark.created_at = row.get("created_at")
    hackathon_row = row.get("hackathons")
    if hackathon_row:
        bookmark.hackathon = _row_to_hackathon(hackathon_row)
    return bookmark

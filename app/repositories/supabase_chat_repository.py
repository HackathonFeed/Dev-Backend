import asyncio
import uuid
from datetime import datetime, timezone

from app.integrations.supabase_client import get_supabase_client


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class SupabaseChatRepository:
    SESSIONS = "ai_chat_sessions"
    MESSAGES = "ai_chat_messages"

    def __init__(self):
        self.client = get_supabase_client()
        if self.client is None:
            raise RuntimeError("Supabase is not configured")

    # ── Sessions ──────────────────────────────────────────────────────────────

    async def create_session(
        self,
        user_id: uuid.UUID,
        title: str = "New Chat",
        hackathon_context: dict | None = None,
    ) -> dict:
        def _create():
            payload = {
                "id": str(uuid.uuid4()),
                "user_id": str(user_id),
                "title": title,
                "hackathon_context": hackathon_context,
                "created_at": _utcnow(),
                "updated_at": _utcnow(),
            }
            response = self.client.table(self.SESSIONS).insert(payload).execute()
            return response.data[0]

        return await asyncio.to_thread(_create)

    async def list_sessions(self, user_id: uuid.UUID, limit: int = 50) -> list[dict]:
        def _fetch():
            response = (
                self.client.table(self.SESSIONS)
                .select("id, title, hackathon_context, created_at, updated_at")
                .eq("user_id", str(user_id))
                .order("updated_at", desc=True)
                .limit(limit)
                .execute()
            )
            return response.data or []

        return await asyncio.to_thread(_fetch)

    async def get_session(self, session_id: str, user_id: uuid.UUID) -> dict | None:
        def _fetch():
            response = (
                self.client.table(self.SESSIONS)
                .select("*")
                .eq("id", session_id)
                .eq("user_id", str(user_id))
                .limit(1)
                .execute()
            )
            return response.data[0] if response.data else None

        return await asyncio.to_thread(_fetch)

    async def update_session(
        self, session_id: str, user_id: uuid.UUID, updates: dict
    ) -> dict | None:
        def _update():
            updates["updated_at"] = _utcnow()
            response = (
                self.client.table(self.SESSIONS)
                .update(updates)
                .eq("id", session_id)
                .eq("user_id", str(user_id))
                .execute()
            )
            return response.data[0] if response.data else None

        return await asyncio.to_thread(_update)

    async def delete_session(self, session_id: str, user_id: uuid.UUID) -> None:
        def _delete():
            self.client.table(self.SESSIONS).delete().eq("id", session_id).eq(
                "user_id", str(user_id)
            ).execute()

        await asyncio.to_thread(_delete)

    # ── Messages ──────────────────────────────────────────────────────────────

    async def get_messages(self, session_id: str) -> list[dict]:
        def _fetch():
            response = (
                self.client.table(self.MESSAGES)
                .select("*")
                .eq("session_id", session_id)
                .order("created_at", desc=False)
                .execute()
            )
            return response.data or []

        return await asyncio.to_thread(_fetch)

    async def add_message(
        self, session_id: str, role: str, content: str
    ) -> dict:
        def _create():
            payload = {
                "id": str(uuid.uuid4()),
                "session_id": session_id,
                "role": role,
                "content": content,
                "created_at": _utcnow(),
            }
            response = self.client.table(self.MESSAGES).insert(payload).execute()
            return response.data[0]

        return await asyncio.to_thread(_create)

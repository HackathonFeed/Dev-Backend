import asyncio
import uuid
from typing import Any

from app.core.constants import UserRole
from app.integrations.supabase_client import get_supabase_client
from app.models.user_model import User


def _row_to_user(row: dict[str, Any]) -> User:
    user = User(
        id=uuid.UUID(row["id"]),
        name=row["name"],
        email=row["email"],
        password_hash=row["password_hash"],
        role=UserRole(row.get("role", UserRole.USER.value)),
        interests=row.get("interests") or [],
    )
    user.created_at = row.get("created_at")
    user.updated_at = row.get("updated_at")
    return user


class SupabaseUserRepository:
    TABLE = "users"

    def __init__(self):
        self.client = get_supabase_client()
        if self.client is None:
            raise RuntimeError("Supabase is not configured")

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        def _fetch():
            response = (
                self.client.table(self.TABLE)
                .select("*")
                .eq("id", str(user_id))
                .limit(1)
                .execute()
            )
            if not response.data:
                return None
            return _row_to_user(response.data[0])

        return await asyncio.to_thread(_fetch)

    async def get_by_email(self, email: str) -> User | None:
        def _fetch():
            response = (
                self.client.table(self.TABLE)
                .select("*")
                .eq("email", email.lower())
                .limit(1)
                .execute()
            )
            if not response.data:
                return None
            return _row_to_user(response.data[0])

        return await asyncio.to_thread(_fetch)

    async def create(self, user: User) -> User:
        def _create():
            payload = {
                "id": str(user.id),
                "name": user.name,
                "email": user.email.lower(),
                "password_hash": user.password_hash,
                "role": user.role.value,
                "interests": user.interests or [],
            }
            response = self.client.table(self.TABLE).insert(payload).execute()
            return _row_to_user(response.data[0])

        return await asyncio.to_thread(_create)

    async def update(self, user: User) -> User:
        def _update():
            payload = {
                "name": user.name,
                "email": user.email.lower(),
                "interests": user.interests or [],
                "role": user.role.value,
            }
            response = (
                self.client.table(self.TABLE)
                .update(payload)
                .eq("id", str(user.id))
                .execute()
            )
            return _row_to_user(response.data[0])

        return await asyncio.to_thread(_update)

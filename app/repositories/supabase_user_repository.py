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
        username=row["username"],
        email=row["email"],
        password_hash=row["password_hash"],
        role=UserRole(row.get("role", UserRole.USER.value)),
        interests=row.get("interests") or [],
    )
    user.avatar_url = row.get("avatar_url")
    user.github_username = row.get("github_username")
    user.linkedin_username = row.get("linkedin_username")
    user.twitter_username = row.get("twitter_username")
    user.website = row.get("website")
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

    async def get_by_username(self, username: str) -> User | None:
        def _fetch():
            response = (
                self.client.table(self.TABLE)
                .select("*")
                .eq("username", username.lower())
                .limit(1)
                .execute()
            )
            if not response.data:
                return None
            return _row_to_user(response.data[0])

        return await asyncio.to_thread(_fetch)

    async def username_exists(self, username: str, *, exclude_user_id: uuid.UUID | None = None) -> bool:
        def _fetch():
            query = self.client.table(self.TABLE).select("id").eq("username", username.lower()).limit(1)
            response = query.execute()
            if not response.data:
                return False
            if exclude_user_id is not None and response.data[0]["id"] == str(exclude_user_id):
                return False
            return True

        return await asyncio.to_thread(_fetch)

    async def create(self, user: User) -> User:
        def _create():
            payload = {
                "id": str(user.id),
                "name": user.name,
                "username": user.username,
                "email": user.email.lower(),
                "password_hash": user.password_hash,
                "role": user.role.value,
                "interests": user.interests or [],
                "avatar_url": user.avatar_url,
            }
            response = self.client.table(self.TABLE).insert(payload).execute()
            if not response.data:
                raise RuntimeError("Supabase did not return created user row")
            return _row_to_user(response.data[0])

        return await asyncio.to_thread(_create)

    async def update(self, user: User) -> User:
        def _update():
            payload = {
                "name": user.name,
                "username": user.username,
                "email": user.email.lower(),
                "interests": user.interests or [],
                "role": user.role.value,
                "avatar_url": user.avatar_url,
                "github_username": user.github_username,
                "linkedin_username": user.linkedin_username,
                "twitter_username": user.twitter_username,
                "website": user.website,
            }
            response = (
                self.client.table(self.TABLE)
                .update(payload)
                .eq("id", str(user.id))
                .execute()
            )
            if not response.data:
                raise RuntimeError("Supabase did not return updated user row")
            return _row_to_user(response.data[0])

        return await asyncio.to_thread(_update)

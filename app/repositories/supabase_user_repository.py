import asyncio
import uuid
from typing import Any

from app.core.constants import SubscriptionPlan, UserRole
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
    user.subscription_plan = SubscriptionPlan(
        row.get("subscription_plan", SubscriptionPlan.HACKER.value)
    )
    user.ai_points = row.get("ai_points", 50)
    user.plan_expires_at = row.get("plan_expires_at")
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
                "subscription_plan": user.subscription_plan.value,
                "ai_points": user.ai_points,
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
                "password_hash": user.password_hash,
                "interests": user.interests or [],
                "role": user.role.value,
                "avatar_url": user.avatar_url,
                "github_username": user.github_username,
                "linkedin_username": user.linkedin_username,
                "twitter_username": user.twitter_username,
                "website": user.website,
                "subscription_plan": user.subscription_plan.value,
                "ai_points": user.ai_points,
                "plan_expires_at": (
                    user.plan_expires_at.isoformat() if user.plan_expires_at else None
                ),
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

    async def deduct_ai_points(self, user_id: uuid.UUID, cost: int) -> User:
        """Atomically deduct points (no-op for unlimited plans). Returns updated user."""
        def _deduct():
            # Fetch current points first
            row = (
                self.client.table(self.TABLE)
                .select("ai_points, subscription_plan")
                .eq("id", str(user_id))
                .limit(1)
                .execute()
            )
            if not row.data:
                raise RuntimeError("User not found for points deduction")
            current = row.data[0]
            if current["ai_points"] == -1:          # unlimited plan
                return None
            new_points = max(current["ai_points"] - cost, 0)
            response = (
                self.client.table(self.TABLE)
                .update({"ai_points": new_points})
                .eq("id", str(user_id))
                .execute()
            )
            if not response.data:
                raise RuntimeError("Supabase did not return updated user after points deduction")
            return _row_to_user(response.data[0])

        result = await asyncio.to_thread(_deduct)
        # If unlimited, just re-fetch the full user
        if result is None:
            return await self.get_by_id(user_id)
        return result

    # ── Admin helpers ─────────────────────────────────────────────────────────

    async def list_all(
        self,
        page: int = 1,
        page_size: int = 25,
        search: str = "",
    ) -> tuple[list[User], int]:
        """Return a page of users + total count. Optionally filter by search string."""
        def _fetch():
            query = self.client.table(self.TABLE).select("*", count="exact")
            if search:
                # Supabase PostgREST OR filter
                query = query.or_(
                    f"name.ilike.%{search}%,email.ilike.%{search}%,username.ilike.%{search}%"
                )
            offset = (page - 1) * page_size
            response = (
                query
                .order("created_at", desc=True)
                .range(offset, offset + page_size - 1)
                .execute()
            )
            users = [_row_to_user(row) for row in (response.data or [])]
            total = response.count or 0
            return users, total

        return await asyncio.to_thread(_fetch)

    async def update_role(self, user_id: uuid.UUID, role: str) -> User:
        def _update():
            response = (
                self.client.table(self.TABLE)
                .update({"role": role})
                .eq("id", str(user_id))
                .execute()
            )
            if not response.data:
                raise RuntimeError("User not found")
            return _row_to_user(response.data[0])

        return await asyncio.to_thread(_update)

    async def update_plan(self, user_id: uuid.UUID, plan: str, ai_points: int) -> User:
        from datetime import datetime, timedelta, timezone
        expires = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat() if plan != "hacker" else None
        def _update():
            response = (
                self.client.table(self.TABLE)
                .update({
                    "subscription_plan": plan,
                    "ai_points": ai_points,
                    "plan_expires_at": expires,
                })
                .eq("id", str(user_id))
                .execute()
            )
            if not response.data:
                raise RuntimeError("User not found")
            return _row_to_user(response.data[0])

        return await asyncio.to_thread(_update)

    async def delete_by_id(self, user_id: uuid.UUID) -> None:
        def _delete():
            self.client.table(self.TABLE).delete().eq("id", str(user_id)).execute()

        await asyncio.to_thread(_delete)

    async def count_by_plan(self) -> dict[str, int]:
        """Return {plan: count} for all plans."""
        def _fetch():
            resp = self.client.table(self.TABLE).select("subscription_plan").execute()
            counts: dict[str, int] = {}
            for row in (resp.data or []):
                p = row.get("subscription_plan", "hacker")
                counts[p] = counts.get(p, 0) + 1
            return counts

        return await asyncio.to_thread(_fetch)

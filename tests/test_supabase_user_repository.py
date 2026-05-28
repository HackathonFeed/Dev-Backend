"""Regression tests for Supabase user persistence payloads."""
import uuid
from datetime import datetime, timezone

import pytest

from app.core.constants import SubscriptionPlan, UserRole
from app.models.user_model import User
from app.repositories.supabase_user_repository import SupabaseUserRepository


class _Response:
    def __init__(self, data):
        self.data = data


class _FakeTable:
    def __init__(self, client):
        self.client = client

    def update(self, payload):
        self.client.updated_payload = payload
        return self

    def eq(self, key, value):
        self.client.eq_filter = (key, value)
        return self

    def execute(self):
        payload = self.client.updated_payload
        row = {
            "id": self.client.user_id,
            "name": payload["name"],
            "username": payload["username"],
            "email": payload["email"],
            "password_hash": payload["password_hash"],
            "role": payload["role"],
            "interests": payload["interests"],
            "avatar_url": payload["avatar_url"],
            "github_username": payload["github_username"],
            "linkedin_username": payload["linkedin_username"],
            "twitter_username": payload["twitter_username"],
            "website": payload["website"],
            "subscription_plan": payload["subscription_plan"],
            "ai_points": payload["ai_points"],
            "plan_expires_at": payload["plan_expires_at"],
        }
        return _Response([row])


class _FakeClient:
    def __init__(self, user_id):
        self.user_id = str(user_id)
        self.updated_payload = None
        self.eq_filter = None

    def table(self, table_name):
        self.table_name = table_name
        return _FakeTable(self)


@pytest.mark.asyncio
async def test_update_persists_password_hash(monkeypatch):
    user_id = uuid.UUID("947b9870-3e5e-49d1-bc34-3cb3cb9860c7")
    fake_client = _FakeClient(user_id)
    monkeypatch.setattr(
        "app.repositories.supabase_user_repository.get_supabase_client",
        lambda: fake_client,
    )

    user = User(
        id=user_id,
        name="Test Hacker",
        username="test-hacker",
        email="Test@HackathonFeed.com",
        password_hash="$2b$12$newhashfromreset",
        role=UserRole.USER,
        subscription_plan=SubscriptionPlan.HACKER,
        ai_points=50,
    )
    user.interests = []
    user.avatar_url = None
    user.created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    user.updated_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    user.plan_expires_at = None

    updated = await SupabaseUserRepository().update(user)

    assert fake_client.table_name == "users"
    assert fake_client.eq_filter == ("id", str(user_id))
    assert fake_client.updated_payload["password_hash"] == "$2b$12$newhashfromreset"
    assert updated.password_hash == "$2b$12$newhashfromreset"

"""Shared fixtures for all test modules."""
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.core.constants import SubscriptionPlan, UserRole
from app.core.security import create_access_token
from app.main import app
from app.models.user_model import User


# ── Reusable User fixtures ────────────────────────────────────────────────────

@pytest.fixture()
def sample_user_id() -> uuid.UUID:
    return uuid.UUID("947b9870-3e5e-49d1-bc34-3cb3cb9860c7")


@pytest.fixture()
def sample_user(sample_user_id: uuid.UUID) -> User:
    user = User(
        id=sample_user_id,
        name="Test Hacker",
        username="test-hacker",
        email="test@hackathonfeed.com",
        password_hash="$2b$12$fakehashfortest",
        role=UserRole.USER,
        subscription_plan=SubscriptionPlan.HACKER,
        ai_points=50,
    )
    user.interests = []
    user.avatar_url = None
    user.created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    user.updated_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    user.plan_expires_at = None
    return user


@pytest.fixture()
def admin_user_id() -> uuid.UUID:
    return uuid.UUID("aaaabbbb-cccc-dddd-eeee-ffffffffffff")


@pytest.fixture()
def admin_user(admin_user_id: uuid.UUID) -> User:
    user = User(
        id=admin_user_id,
        name="Admin User",
        username="admin-user",
        email="mdabucse@gmail.com",
        password_hash="$2b$12$fakehashforadmin",
        role=UserRole.ADMIN,
        subscription_plan=SubscriptionPlan.CHAMPION,
        ai_points=-1,
    )
    user.interests = []
    user.avatar_url = None
    user.created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    user.updated_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    user.plan_expires_at = None
    return user


# ── Auth headers ──────────────────────────────────────────────────────────────

@pytest.fixture()
def user_auth_headers(sample_user: User) -> dict:
    token = create_access_token(str(sample_user.id), sample_user.email, sample_user.role)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def admin_auth_headers(admin_user: User) -> dict:
    token = create_access_token(str(admin_user.id), admin_user.email, admin_user.role)
    return {"Authorization": f"Bearer {token}"}


# ── Mock repository factories ─────────────────────────────────────────────────

@pytest.fixture()
def mock_user_repo(sample_user: User):
    repo = MagicMock()
    repo.get_by_email = AsyncMock(return_value=None)
    repo.get_by_id = AsyncMock(return_value=sample_user)
    repo.create = AsyncMock(return_value=sample_user)
    repo.update = AsyncMock(return_value=sample_user)
    repo.username_exists = AsyncMock(return_value=False)
    repo.list_all = AsyncMock(return_value=([sample_user], 1))
    repo.count_by_plan = AsyncMock(return_value={"hacker": 10, "builder": 3, "champion": 1})
    repo.update_role = AsyncMock(return_value=sample_user)
    repo.update_plan = AsyncMock(return_value=sample_user)
    repo.delete_by_id = AsyncMock(return_value=None)
    return repo


# ── TestClient ────────────────────────────────────────────────────────────────

@pytest.fixture()
def client() -> TestClient:
    return TestClient(app, raise_server_exceptions=True)

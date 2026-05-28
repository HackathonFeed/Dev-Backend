"""Integration tests for /admin/* routes using mocked repositories + services."""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies.auth_dependency import get_current_user, require_admin
from app.core.constants import SubscriptionPlan, UserRole
from app.main import app
from app.models.user_model import User
from app.schemas.admin_schema import AdminUserRow
from datetime import datetime, timezone

client = TestClient(app, raise_server_exceptions=False)

BASE = "/api/v1/admin"

_ADMIN_ID = uuid.UUID("aaaabbbb-cccc-dddd-eeee-ffffffffffff")
_USER_ID  = uuid.UUID("947b9870-3e5e-49d1-bc34-3cb3cb9860c7")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_admin() -> User:
    u = User(
        id=_ADMIN_ID,
        name="Admin User",
        username="admin-user",
        email="mdabucse@gmail.com",
        password_hash="$2b$12$fakehash",
        role=UserRole.ADMIN,
        subscription_plan=SubscriptionPlan.CHAMPION,
        ai_points=-1,
    )
    u.interests = []
    u.avatar_url = None
    u.created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    u.updated_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    u.plan_expires_at = None
    return u


def _make_user() -> User:
    u = User(
        id=_USER_ID,
        name="Regular User",
        username="regular-user",
        email="user@hackathonfeed.com",
        password_hash="$2b$12$fakehash",
        role=UserRole.USER,
        subscription_plan=SubscriptionPlan.HACKER,
        ai_points=50,
    )
    u.interests = []
    u.avatar_url = None
    u.created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    u.updated_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    u.plan_expires_at = None
    return u


def _mock_repo(admin: User, target_user: User | None = None):
    """Build a mock user repository for admin endpoint calls."""
    repo = MagicMock()
    repo.get_by_id    = AsyncMock(return_value=target_user or _make_user())
    repo.list_all     = AsyncMock(return_value=([_make_user()], 1))
    repo.count_by_plan = AsyncMock(return_value={"hacker": 10, "builder": 3, "champion": 1})
    repo.update_role  = AsyncMock(return_value=_make_user())
    repo.update_plan  = AsyncMock(return_value=_make_user())
    repo.delete_by_id = AsyncMock(return_value=None)
    return repo


def _admin_override(admin: User):
    """Return a FastAPI dependency override that yields *admin*."""
    async def _dep():
        return admin
    return _dep


def _user_override(user: User):
    """Return a FastAPI dependency override that yields *user* (non-admin)."""
    async def _dep():
        return user
    return _dep


# ── GET /admin/stats ──────────────────────────────────────────────────────────

class TestGetAdminStats:
    def test_admin_gets_stats(self):
        admin = _make_admin()
        mock_stats = {"total_users": 14, "total_hackathons": 5}

        with patch("app.services.analytics_service.AnalyticsService.get_dashboard_stats",
                   new=AsyncMock(return_value=mock_stats)):
            app.dependency_overrides[require_admin] = _admin_override(admin)
            try:
                res = client.get(f"{BASE}/stats")
            finally:
                app.dependency_overrides.pop(require_admin, None)

        assert res.status_code == 200
        body = res.json()
        assert body["success"] is True
        assert body["data"]["total_users"] == 14

    def test_non_admin_gets_403(self):
        user = _make_user()
        app.dependency_overrides[get_current_user] = _user_override(user)
        try:
            res = client.get(f"{BASE}/stats")
        finally:
            app.dependency_overrides.pop(get_current_user, None)

        assert res.status_code == 403

    def test_unauthenticated_gets_401_or_403(self):
        res = client.get(f"{BASE}/stats")
        assert res.status_code in (401, 403)


# ── GET /admin/users ──────────────────────────────────────────────────────────

class TestListUsers:
    def test_admin_gets_user_list(self):
        admin = _make_admin()
        repo  = _mock_repo(admin)

        with patch("app.repositories.factory.get_user_repository", return_value=repo):
            app.dependency_overrides[require_admin] = _admin_override(admin)
            try:
                res = client.get(f"{BASE}/users")
            finally:
                app.dependency_overrides.pop(require_admin, None)

        assert res.status_code == 200
        body = res.json()
        assert body["success"] is True
        assert body["data"]["total"] == 1
        assert len(body["data"]["items"]) == 1

    def test_non_admin_gets_403(self):
        user = _make_user()
        app.dependency_overrides[get_current_user] = _user_override(user)
        try:
            res = client.get(f"{BASE}/users")
        finally:
            app.dependency_overrides.pop(get_current_user, None)

        assert res.status_code == 403

    def test_pagination_params_forwarded(self):
        admin = _make_admin()
        repo  = _mock_repo(admin)

        with patch("app.repositories.factory.get_user_repository", return_value=repo):
            app.dependency_overrides[require_admin] = _admin_override(admin)
            try:
                res = client.get(f"{BASE}/users?page=2&page_size=10")
            finally:
                app.dependency_overrides.pop(require_admin, None)

        assert res.status_code == 200
        body = res.json()
        assert body["data"]["page"] == 2
        assert body["data"]["page_size"] == 10

    def test_search_param_accepted(self):
        admin = _make_admin()
        repo  = _mock_repo(admin)

        with patch("app.repositories.factory.get_user_repository", return_value=repo):
            app.dependency_overrides[require_admin] = _admin_override(admin)
            try:
                res = client.get(f"{BASE}/users?search=hacker")
            finally:
                app.dependency_overrides.pop(require_admin, None)

        assert res.status_code == 200
        # repo.list_all must have been called (no assertion on call args — just 200)

    def test_response_contains_id_as_string(self):
        admin = _make_admin()
        repo  = _mock_repo(admin)

        with patch("app.repositories.factory.get_user_repository", return_value=repo):
            app.dependency_overrides[require_admin] = _admin_override(admin)
            try:
                res = client.get(f"{BASE}/users")
            finally:
                app.dependency_overrides.pop(require_admin, None)

        item = res.json()["data"]["items"][0]
        assert isinstance(item["id"], str)


# ── GET /admin/users/plan-counts ──────────────────────────────────────────────

class TestPlanCounts:
    def test_admin_gets_plan_counts(self):
        admin = _make_admin()
        repo  = _mock_repo(admin)

        with patch("app.repositories.factory.get_user_repository", return_value=repo):
            app.dependency_overrides[require_admin] = _admin_override(admin)
            try:
                res = client.get(f"{BASE}/users/plan-counts")
            finally:
                app.dependency_overrides.pop(require_admin, None)

        assert res.status_code == 200
        body = res.json()
        assert body["success"] is True
        assert body["data"]["hacker"] == 10

    def test_non_admin_gets_403(self):
        user = _make_user()
        app.dependency_overrides[get_current_user] = _user_override(user)
        try:
            res = client.get(f"{BASE}/users/plan-counts")
        finally:
            app.dependency_overrides.pop(get_current_user, None)

        assert res.status_code == 403

    def test_all_plans_in_response(self):
        admin = _make_admin()
        repo  = _mock_repo(admin)

        with patch("app.repositories.factory.get_user_repository", return_value=repo):
            app.dependency_overrides[require_admin] = _admin_override(admin)
            try:
                res = client.get(f"{BASE}/users/plan-counts")
            finally:
                app.dependency_overrides.pop(require_admin, None)

        data = res.json()["data"]
        assert "hacker" in data
        assert "builder" in data
        assert "champion" in data


# ── PATCH /admin/users/{user_id}/role ─────────────────────────────────────────

class TestUpdateUserRole:
    def test_admin_can_update_role(self):
        admin    = _make_admin()
        updated  = _make_user()
        updated.role = UserRole.MODERATOR
        repo = _mock_repo(admin, updated)
        repo.update_role = AsyncMock(return_value=updated)

        with patch("app.repositories.factory.get_user_repository", return_value=repo):
            app.dependency_overrides[require_admin] = _admin_override(admin)
            try:
                res = client.patch(
                    f"{BASE}/users/{_USER_ID}/role",
                    json={"role": "moderator"},
                )
            finally:
                app.dependency_overrides.pop(require_admin, None)

        assert res.status_code == 200
        assert res.json()["success"] is True

    def test_admin_cannot_change_own_role(self):
        admin = _make_admin()
        repo  = _mock_repo(admin)

        with patch("app.repositories.factory.get_user_repository", return_value=repo):
            app.dependency_overrides[require_admin] = _admin_override(admin)
            try:
                res = client.patch(
                    f"{BASE}/users/{_ADMIN_ID}/role",
                    json={"role": "user"},
                )
            finally:
                app.dependency_overrides.pop(require_admin, None)

        assert res.status_code == 400

    def test_invalid_role_returns_422(self):
        admin = _make_admin()
        repo  = _mock_repo(admin)

        with patch("app.repositories.factory.get_user_repository", return_value=repo):
            app.dependency_overrides[require_admin] = _admin_override(admin)
            try:
                res = client.patch(
                    f"{BASE}/users/{_USER_ID}/role",
                    json={"role": "superuser"},
                )
            finally:
                app.dependency_overrides.pop(require_admin, None)

        assert res.status_code == 422

    def test_non_admin_gets_403(self):
        user = _make_user()
        app.dependency_overrides[get_current_user] = _user_override(user)
        try:
            res = client.patch(
                f"{BASE}/users/{_USER_ID}/role",
                json={"role": "moderator"},
            )
        finally:
            app.dependency_overrides.pop(get_current_user, None)

        assert res.status_code == 403


# ── PATCH /admin/users/{user_id}/plan ─────────────────────────────────────────

class TestUpdateUserPlan:
    def test_admin_can_update_plan(self):
        admin   = _make_admin()
        updated = _make_user()
        updated.subscription_plan = SubscriptionPlan.BUILDER
        updated.ai_points = 200
        repo = _mock_repo(admin, updated)
        repo.update_plan = AsyncMock(return_value=updated)

        with patch("app.repositories.factory.get_user_repository", return_value=repo):
            app.dependency_overrides[require_admin] = _admin_override(admin)
            try:
                res = client.patch(
                    f"{BASE}/users/{_USER_ID}/plan",
                    json={"plan": "builder"},
                )
            finally:
                app.dependency_overrides.pop(require_admin, None)

        assert res.status_code == 200
        assert res.json()["success"] is True

    def test_invalid_plan_returns_422(self):
        admin = _make_admin()
        repo  = _mock_repo(admin)

        with patch("app.repositories.factory.get_user_repository", return_value=repo):
            app.dependency_overrides[require_admin] = _admin_override(admin)
            try:
                res = client.patch(
                    f"{BASE}/users/{_USER_ID}/plan",
                    json={"plan": "premium"},
                )
            finally:
                app.dependency_overrides.pop(require_admin, None)

        assert res.status_code == 422

    def test_non_admin_gets_403(self):
        user = _make_user()
        app.dependency_overrides[get_current_user] = _user_override(user)
        try:
            res = client.patch(
                f"{BASE}/users/{_USER_ID}/plan",
                json={"plan": "builder"},
            )
        finally:
            app.dependency_overrides.pop(get_current_user, None)

        assert res.status_code == 403


# ── DELETE /admin/users/{user_id} ─────────────────────────────────────────────

class TestDeleteUser:
    def test_admin_can_delete_other_user(self):
        admin = _make_admin()
        repo  = _mock_repo(admin)

        with patch("app.repositories.factory.get_user_repository", return_value=repo):
            app.dependency_overrides[require_admin] = _admin_override(admin)
            try:
                res = client.delete(f"{BASE}/users/{_USER_ID}")
            finally:
                app.dependency_overrides.pop(require_admin, None)

        assert res.status_code == 200
        assert res.json()["success"] is True

    def test_admin_cannot_delete_own_account(self):
        admin = _make_admin()
        repo  = _mock_repo(admin)

        with patch("app.repositories.factory.get_user_repository", return_value=repo):
            app.dependency_overrides[require_admin] = _admin_override(admin)
            try:
                res = client.delete(f"{BASE}/users/{_ADMIN_ID}")
            finally:
                app.dependency_overrides.pop(require_admin, None)

        assert res.status_code == 400

    def test_non_admin_gets_403(self):
        user = _make_user()
        app.dependency_overrides[get_current_user] = _user_override(user)
        try:
            res = client.delete(f"{BASE}/users/{_USER_ID}")
        finally:
            app.dependency_overrides.pop(get_current_user, None)

        assert res.status_code == 403


# ── POST /admin/scrape ────────────────────────────────────────────────────────

class TestTriggerScrape:
    def test_admin_can_trigger_scrape(self):
        admin = _make_admin()
        app.dependency_overrides[require_admin] = _admin_override(admin)
        try:
            res = client.post(f"{BASE}/scrape")
        finally:
            app.dependency_overrides.pop(require_admin, None)

        assert res.status_code == 200
        assert res.json()["data"]["status"] == "queued"

    def test_non_admin_gets_403(self):
        user = _make_user()
        app.dependency_overrides[get_current_user] = _user_override(user)
        try:
            res = client.post(f"{BASE}/scrape")
        finally:
            app.dependency_overrides.pop(get_current_user, None)

        assert res.status_code == 403


# ── POST /admin/generate-embeddings ──────────────────────────────────────────

class TestGenerateEmbeddings:
    def test_admin_can_trigger_embeddings(self):
        admin = _make_admin()

        with patch("app.services.embedding_service.generate_missing_embeddings",
                   new=AsyncMock(return_value=None)):
            app.dependency_overrides[require_admin] = _admin_override(admin)
            try:
                res = client.post(f"{BASE}/generate-embeddings")
            finally:
                app.dependency_overrides.pop(require_admin, None)

        assert res.status_code == 200
        assert res.json()["data"]["status"] == "running"

    def test_non_admin_gets_403(self):
        user = _make_user()
        app.dependency_overrides[get_current_user] = _user_override(user)
        try:
            res = client.post(f"{BASE}/generate-embeddings")
        finally:
            app.dependency_overrides.pop(get_current_user, None)

        assert res.status_code == 403

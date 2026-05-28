"""Integration tests for /auth/* routes using mocked repositories."""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.security import hash_password, verify_password
from app.main import app
from app.services import password_reset_service as prs

client = TestClient(app, raise_server_exceptions=False)

BASE = "/api/v1/auth"


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_user(email: str = "test@hackathonfeed.com"):
    """Build a minimal user-like object for mock returns."""
    from app.models.user_model import User
    from app.core.constants import SubscriptionPlan, UserRole
    from datetime import datetime, timezone

    u = User(
        id=uuid.uuid4(),
        name="Test Hacker",
        username="test-hacker",
        email=email,
        password_hash=hash_password("password123"),
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


@pytest.fixture(autouse=True)
def clean_prs():
    prs._reset_codes.clear()
    prs._reset_tokens.clear()
    yield
    prs._reset_codes.clear()
    prs._reset_tokens.clear()


# ── POST /auth/register ───────────────────────────────────────────────────────

class TestRegister:
    def test_register_success(self):
        user = _make_user()
        mock_repo = MagicMock()
        mock_repo.get_by_email = AsyncMock(return_value=None)
        mock_repo.username_exists = AsyncMock(return_value=False)
        mock_repo.create = AsyncMock(return_value=user)

        with patch("app.repositories.factory.get_user_repository", return_value=mock_repo), \
             patch("app.services.email_service.EmailService.send_welcome_bg"):
            res = client.post(f"{BASE}/register", json={
                "name": "Test Hacker",
                "email": "test@hackathonfeed.com",
                "password": "password123",
            })

        assert res.status_code == 200
        body = res.json()
        assert body["success"] is True
        assert "access_token" in body["data"]
        assert "refresh_token" in body["data"]

    def test_register_duplicate_email_returns_409(self):
        existing_user = _make_user()
        mock_repo = MagicMock()
        mock_repo.get_by_email = AsyncMock(return_value=existing_user)

        with patch("app.repositories.factory.get_user_repository", return_value=mock_repo):
            res = client.post(f"{BASE}/register", json={
                "name": "Test Hacker",
                "email": "test@hackathonfeed.com",
                "password": "password123",
            })

        assert res.status_code == 409

    def test_register_missing_name_returns_422(self):
        res = client.post(f"{BASE}/register", json={
            "email": "test@hackathonfeed.com",
            "password": "password123",
        })
        assert res.status_code == 422

    def test_register_invalid_email_returns_422(self):
        res = client.post(f"{BASE}/register", json={
            "name": "Test",
            "email": "not-an-email",
            "password": "password123",
        })
        assert res.status_code == 422

    def test_register_short_password_returns_422(self):
        res = client.post(f"{BASE}/register", json={
            "name": "Test",
            "email": "test@hackathonfeed.com",
            "password": "short",
        })
        assert res.status_code == 422


# ── POST /auth/login ──────────────────────────────────────────────────────────

class TestLogin:
    def test_login_success(self):
        user = _make_user()
        mock_repo = MagicMock()
        mock_repo.get_by_email = AsyncMock(return_value=user)

        with patch("app.repositories.factory.get_user_repository", return_value=mock_repo):
            res = client.post(f"{BASE}/login", json={
                "email": "test@hackathonfeed.com",
                "password": "password123",
            })

        assert res.status_code == 200
        body = res.json()
        assert body["success"] is True
        assert "access_token" in body["data"]

    def test_login_wrong_password_returns_401(self):
        user = _make_user()
        mock_repo = MagicMock()
        mock_repo.get_by_email = AsyncMock(return_value=user)

        with patch("app.repositories.factory.get_user_repository", return_value=mock_repo):
            res = client.post(f"{BASE}/login", json={
                "email": "test@hackathonfeed.com",
                "password": "wrongpassword",
            })

        assert res.status_code == 401

    def test_login_unknown_email_returns_401(self):
        mock_repo = MagicMock()
        mock_repo.get_by_email = AsyncMock(return_value=None)

        with patch("app.repositories.factory.get_user_repository", return_value=mock_repo):
            res = client.post(f"{BASE}/login", json={
                "email": "ghost@hackathonfeed.com",
                "password": "password123",
            })

        assert res.status_code == 401

    def test_login_missing_email_returns_422(self):
        res = client.post(f"{BASE}/login", json={"password": "password123"})
        assert res.status_code == 422


# ── POST /auth/forgot-password ────────────────────────────────────────────────

class TestForgotPassword:
    def test_known_email_returns_200(self):
        user = _make_user()
        mock_repo = MagicMock()
        mock_repo.get_by_email = AsyncMock(return_value=user)

        with patch("app.repositories.factory.get_user_repository", return_value=mock_repo), \
             patch("app.services.email_service.EmailService.send_reset_code_bg"):
            res = client.post(f"{BASE}/forgot-password", json={"email": "test@hackathonfeed.com"})

        assert res.status_code == 200
        assert res.json()["success"] is True

    def test_unknown_email_still_returns_200(self):
        """User enumeration prevention — always 200."""
        mock_repo = MagicMock()
        mock_repo.get_by_email = AsyncMock(return_value=None)

        with patch("app.repositories.factory.get_user_repository", return_value=mock_repo):
            res = client.post(f"{BASE}/forgot-password", json={"email": "ghost@example.com"})

        assert res.status_code == 200

    def test_known_email_stores_otp(self):
        user = _make_user("store@hackathonfeed.com")
        mock_repo = MagicMock()
        mock_repo.get_by_email = AsyncMock(return_value=user)

        with patch("app.repositories.factory.get_user_repository", return_value=mock_repo), \
             patch("app.services.email_service.EmailService.send_reset_code_bg"):
            client.post(f"{BASE}/forgot-password", json={"email": "store@hackathonfeed.com"})

        assert "store@hackathonfeed.com" in prs._reset_codes

    def test_invalid_email_returns_422(self):
        res = client.post(f"{BASE}/forgot-password", json={"email": "not-an-email"})
        assert res.status_code == 422


# ── POST /auth/verify-reset-code ──────────────────────────────────────────────

class TestVerifyResetCode:
    def test_valid_code_returns_reset_token(self):
        code = prs.generate_and_store_code("verify@hackathonfeed.com")
        res = client.post(f"{BASE}/verify-reset-code", json={
            "email": "verify@hackathonfeed.com",
            "code": code,
        })
        assert res.status_code == 200
        body = res.json()
        assert body["success"] is True
        assert "reset_token" in body["data"]

    def test_wrong_code_returns_400(self):
        prs.generate_and_store_code("verify@hackathonfeed.com")
        res = client.post(f"{BASE}/verify-reset-code", json={
            "email": "verify@hackathonfeed.com",
            "code": "000000",
        })
        assert res.status_code == 400

    def test_no_code_stored_returns_400(self):
        res = client.post(f"{BASE}/verify-reset-code", json={
            "email": "nobody@hackathonfeed.com",
            "code": "123456",
        })
        assert res.status_code == 400

    def test_code_wrong_length_returns_422(self):
        res = client.post(f"{BASE}/verify-reset-code", json={
            "email": "u@h.com",
            "code": "12345",
        })
        assert res.status_code == 422


# ── POST /auth/reset-password ─────────────────────────────────────────────────

class TestResetPassword:
    def _issue_token(self, email: str = "reset@hackathonfeed.com") -> str:
        code = prs.generate_and_store_code(email)
        return prs.verify_code_and_issue_token(email, code)

    def test_valid_token_resets_password(self):
        user = _make_user("reset@hackathonfeed.com")
        token = self._issue_token("reset@hackathonfeed.com")

        mock_repo = MagicMock()
        mock_repo.get_by_email = AsyncMock(return_value=user)
        mock_repo.update = AsyncMock(return_value=user)

        with patch("app.repositories.factory.get_user_repository", return_value=mock_repo):
            res = client.post(f"{BASE}/reset-password", json={
                "reset_token": token,
                "new_password": "brandnewpassword",
            })

        assert res.status_code == 200
        assert res.json()["success"] is True
        mock_repo.update.assert_awaited_once()
        updated_user = mock_repo.update.await_args.args[0]
        assert verify_password("brandnewpassword", updated_user.password_hash)
        assert not verify_password("password123", updated_user.password_hash)

    def test_invalid_token_returns_400(self):
        res = client.post(f"{BASE}/reset-password", json={
            "reset_token": "fake-token-that-does-not-exist",
            "new_password": "brandnewpassword",
        })
        assert res.status_code == 400

    def test_token_is_single_use(self):
        user = _make_user("singleuse@hackathonfeed.com")
        token = self._issue_token("singleuse@hackathonfeed.com")

        mock_repo = MagicMock()
        mock_repo.get_by_email = AsyncMock(return_value=user)
        mock_repo.update = AsyncMock(return_value=user)

        with patch("app.repositories.factory.get_user_repository", return_value=mock_repo):
            first = client.post(f"{BASE}/reset-password", json={
                "reset_token": token,
                "new_password": "firstpassword1",
            })
            second = client.post(f"{BASE}/reset-password", json={
                "reset_token": token,
                "new_password": "secondpassword2",
            })

        assert first.status_code == 200
        assert second.status_code == 400

    def test_short_password_returns_422(self):
        res = client.post(f"{BASE}/reset-password", json={
            "reset_token": "sometoken",
            "new_password": "short",
        })
        assert res.status_code == 422

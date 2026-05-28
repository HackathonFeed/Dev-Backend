"""Unit tests for password hashing and JWT token utilities."""
from datetime import timedelta

import pytest

from app.core.constants import UserRole
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
    verify_token,
)

USER_ID = "947b9870-3e5e-49d1-bc34-3cb3cb9860c7"
EMAIL = "test@hackathonfeed.com"
ROLE = UserRole.USER


# ── Password hashing ──────────────────────────────────────────────────────────

class TestPasswordHashing:
    def test_hash_is_not_plaintext(self):
        hashed = hash_password("mysecretpassword")
        assert hashed != "mysecretpassword"

    def test_hash_starts_with_bcrypt_prefix(self):
        hashed = hash_password("mysecretpassword")
        assert hashed.startswith("$2b$") or hashed.startswith("$2a$")

    def test_same_password_produces_different_hashes(self):
        h1 = hash_password("password123")
        h2 = hash_password("password123")
        assert h1 != h2  # bcrypt uses random salt

    def test_verify_correct_password_returns_true(self):
        hashed = hash_password("correcthorsebatterystaple")
        assert verify_password("correcthorsebatterystaple", hashed) is True

    def test_verify_wrong_password_returns_false(self):
        hashed = hash_password("correcthorsebatterystaple")
        assert verify_password("wrongpassword", hashed) is False

    def test_verify_empty_string_returns_false(self):
        hashed = hash_password("nonempty")
        assert verify_password("", hashed) is False

    def test_verify_case_sensitivity(self):
        hashed = hash_password("CaseSensitive")
        assert verify_password("casesensitive", hashed) is False
        assert verify_password("CaseSensitive", hashed) is True


# ── JWT Access Token ──────────────────────────────────────────────────────────

class TestAccessToken:
    def test_create_access_token_returns_string(self):
        token = create_access_token(USER_ID, EMAIL, ROLE)
        assert isinstance(token, str)
        assert len(token) > 20

    def test_verify_access_token_returns_payload(self):
        token = create_access_token(USER_ID, EMAIL, ROLE)
        payload = verify_token(token, expected_type="access")
        assert payload is not None
        assert payload["sub"] == USER_ID
        assert payload["email"] == EMAIL
        assert payload["type"] == "access"

    def test_verify_wrong_type_returns_none(self):
        token = create_access_token(USER_ID, EMAIL, ROLE)
        result = verify_token(token, expected_type="refresh")
        assert result is None

    def test_verify_tampered_token_returns_none(self):
        token = create_access_token(USER_ID, EMAIL, ROLE)
        tampered = token[:-5] + "XXXXX"
        result = verify_token(tampered, expected_type="access")
        assert result is None

    def test_verify_garbage_string_returns_none(self):
        result = verify_token("not.a.valid.jwt", expected_type="access")
        assert result is None

    def test_expired_token_returns_none(self):
        token = create_access_token(
            USER_ID, EMAIL, ROLE, expires_delta=timedelta(seconds=-1)
        )
        result = verify_token(token, expected_type="access")
        assert result is None

    def test_role_stored_in_payload(self):
        token = create_access_token(USER_ID, EMAIL, UserRole.ADMIN)
        payload = verify_token(token, expected_type="access")
        assert payload["role"] == "admin"

    def test_admin_role_stored_correctly(self):
        token = create_access_token(USER_ID, EMAIL, UserRole.ADMIN)
        payload = verify_token(token)
        assert payload["role"] == UserRole.ADMIN.value


# ── JWT Refresh Token ─────────────────────────────────────────────────────────

class TestRefreshToken:
    def test_create_refresh_token_returns_string(self):
        token = create_refresh_token(USER_ID, EMAIL, ROLE)
        assert isinstance(token, str)

    def test_verify_refresh_token_succeeds(self):
        token = create_refresh_token(USER_ID, EMAIL, ROLE)
        payload = verify_token(token, expected_type="refresh")
        assert payload is not None
        assert payload["sub"] == USER_ID
        assert payload["type"] == "refresh"

    def test_refresh_token_rejected_as_access(self):
        token = create_refresh_token(USER_ID, EMAIL, ROLE)
        result = verify_token(token, expected_type="access")
        assert result is None

    def test_access_token_rejected_as_refresh(self):
        token = create_access_token(USER_ID, EMAIL, ROLE)
        result = verify_token(token, expected_type="refresh")
        assert result is None

    def test_access_and_refresh_tokens_differ(self):
        access = create_access_token(USER_ID, EMAIL, ROLE)
        refresh = create_refresh_token(USER_ID, EMAIL, ROLE)
        assert access != refresh

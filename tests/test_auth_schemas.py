"""Unit tests for authentication Pydantic schemas."""
import pytest
from pydantic import ValidationError

from app.schemas.auth_schema import (
    ForgotPasswordRequest,
    ResetPasswordRequest,
    UserLoginRequest,
    UserRegisterRequest,
    VerifyResetCodeRequest,
)


# ── UserRegisterRequest ───────────────────────────────────────────────────────

class TestUserRegisterRequest:
    def test_valid_registration(self):
        req = UserRegisterRequest(
            name="Mohamed Abubakkar",
            email="test@hackathonfeed.com",
            password="securepass123",
        )
        assert req.name == "Mohamed Abubakkar"
        assert req.email == "test@hackathonfeed.com"

    def test_name_too_short_raises(self):
        with pytest.raises(ValidationError):
            UserRegisterRequest(name="A", email="x@y.com", password="password123")

    def test_name_too_long_raises(self):
        with pytest.raises(ValidationError):
            UserRegisterRequest(name="A" * 256, email="x@y.com", password="password123")

    def test_invalid_email_raises(self):
        with pytest.raises(ValidationError):
            UserRegisterRequest(name="Test User", email="not-an-email", password="password123")

    def test_password_too_short_raises(self):
        with pytest.raises(ValidationError):
            UserRegisterRequest(name="Test User", email="x@y.com", password="short")

    def test_password_max_128_chars(self):
        req = UserRegisterRequest(name="Test", email="x@y.com", password="p" * 128)
        assert len(req.password) == 128

    def test_password_over_128_chars_raises(self):
        with pytest.raises(ValidationError):
            UserRegisterRequest(name="Test", email="x@y.com", password="p" * 129)


# ── UserLoginRequest ──────────────────────────────────────────────────────────

class TestUserLoginRequest:
    def test_valid_login(self):
        req = UserLoginRequest(email="user@example.com", password="anypassword")
        assert req.email == "user@example.com"

    def test_invalid_email_raises(self):
        with pytest.raises(ValidationError):
            UserLoginRequest(email="invalid", password="pass")

    def test_missing_password_raises(self):
        with pytest.raises(ValidationError):
            UserLoginRequest(email="user@example.com")


# ── ForgotPasswordRequest ─────────────────────────────────────────────────────

class TestForgotPasswordRequest:
    def test_valid_email(self):
        req = ForgotPasswordRequest(email="user@hackathonfeed.com")
        assert str(req.email) == "user@hackathonfeed.com"

    def test_invalid_email_raises(self):
        with pytest.raises(ValidationError):
            ForgotPasswordRequest(email="not-an-email")

    def test_missing_email_raises(self):
        with pytest.raises(ValidationError):
            ForgotPasswordRequest()

    def test_email_normalised_to_lowercase(self):
        req = ForgotPasswordRequest(email="User@HackathonFeed.COM")
        assert str(req.email) == "user@hackathonfeed.com"


# ── VerifyResetCodeRequest ────────────────────────────────────────────────────

class TestVerifyResetCodeRequest:
    def test_valid_request(self):
        req = VerifyResetCodeRequest(email="user@hackathonfeed.com", code="123456")
        assert req.code == "123456"

    def test_code_too_short_raises(self):
        with pytest.raises(ValidationError):
            VerifyResetCodeRequest(email="u@h.com", code="12345")

    def test_code_too_long_raises(self):
        with pytest.raises(ValidationError):
            VerifyResetCodeRequest(email="u@h.com", code="1234567")

    def test_invalid_email_raises(self):
        with pytest.raises(ValidationError):
            VerifyResetCodeRequest(email="bad-email", code="123456")

    def test_missing_code_raises(self):
        with pytest.raises(ValidationError):
            VerifyResetCodeRequest(email="u@h.com")


# ── ResetPasswordRequest ──────────────────────────────────────────────────────

class TestResetPasswordRequest:
    def test_valid_request(self):
        req = ResetPasswordRequest(reset_token="some-valid-token", new_password="newsecurepass")
        assert req.new_password == "newsecurepass"

    def test_short_password_raises(self):
        with pytest.raises(ValidationError):
            ResetPasswordRequest(reset_token="token", new_password="short")

    def test_password_too_long_raises(self):
        with pytest.raises(ValidationError):
            ResetPasswordRequest(reset_token="token", new_password="p" * 129)

    def test_missing_token_raises(self):
        with pytest.raises(ValidationError):
            ResetPasswordRequest(new_password="securepassword")

    def test_exactly_8_chars_allowed(self):
        req = ResetPasswordRequest(reset_token="tok", new_password="12345678")
        assert len(req.new_password) == 8

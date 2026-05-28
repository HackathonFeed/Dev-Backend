"""Unit tests for the in-memory password-reset OTP service."""
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from app.services import password_reset_service as prs


# ── Helpers ───────────────────────────────────────────────────────────────────

EMAIL = "user@hackathonfeed.com"


def _clear_stores():
    """Wipe module-level dicts between tests."""
    prs._reset_codes.clear()
    prs._reset_tokens.clear()


@pytest.fixture(autouse=True)
def clean_stores():
    _clear_stores()
    yield
    _clear_stores()


# ── generate_and_store_code ───────────────────────────────────────────────────

class TestGenerateAndStoreCode:
    def test_returns_six_digit_string(self):
        code = prs.generate_and_store_code(EMAIL)
        assert len(code) == 6
        assert code.isdigit()

    def test_stores_entry_for_email(self):
        prs.generate_and_store_code(EMAIL)
        assert EMAIL.lower() in prs._reset_codes

    def test_normalises_email_to_lowercase(self):
        prs.generate_and_store_code("USER@HACKATHONFEED.COM")
        assert "user@hackathonfeed.com" in prs._reset_codes

    def test_overwrites_previous_code(self):
        prs.generate_and_store_code(EMAIL)
        second = prs.generate_and_store_code(EMAIL)
        assert prs._reset_codes[EMAIL].code == second  # NamedTuple attr access
        # Only one entry should exist (the most recent)
        assert len(prs._reset_codes) == 1

    def test_entry_has_future_expiry(self):
        prs.generate_and_store_code(EMAIL)
        entry = prs._reset_codes[EMAIL]
        assert entry.expires_at > datetime.now(timezone.utc)

    def test_expiry_is_approximately_15_minutes(self):
        prs.generate_and_store_code(EMAIL)
        entry = prs._reset_codes[EMAIL]
        diff = entry.expires_at - datetime.now(timezone.utc)
        assert 14 * 60 < diff.total_seconds() <= 15 * 60 + 5


# ── verify_code_and_issue_token ───────────────────────────────────────────────

class TestVerifyCodeAndIssueToken:
    def test_valid_code_returns_token(self):
        code = prs.generate_and_store_code(EMAIL)
        token = prs.verify_code_and_issue_token(EMAIL, code)
        assert token is not None
        assert len(token) > 10

    def test_valid_code_consumes_otp_entry(self):
        code = prs.generate_and_store_code(EMAIL)
        prs.verify_code_and_issue_token(EMAIL, code)
        assert EMAIL not in prs._reset_codes

    def test_valid_code_stores_reset_token(self):
        code = prs.generate_and_store_code(EMAIL)
        token = prs.verify_code_and_issue_token(EMAIL, code)
        assert token in prs._reset_tokens

    def test_wrong_code_returns_none(self):
        prs.generate_and_store_code(EMAIL)
        result = prs.verify_code_and_issue_token(EMAIL, "000000")
        assert result is None

    def test_wrong_code_also_consumes_entry(self):
        """OTP entry is popped even on wrong code to prevent brute force reuse."""
        prs.generate_and_store_code(EMAIL)
        prs.verify_code_and_issue_token(EMAIL, "000000")
        assert EMAIL not in prs._reset_codes

    def test_unknown_email_returns_none(self):
        result = prs.verify_code_and_issue_token("ghost@hackathonfeed.com", "123456")
        assert result is None

    def test_expired_code_returns_none(self):
        code = prs.generate_and_store_code(EMAIL)
        # Back-date the expiry
        entry = prs._reset_codes[EMAIL]
        prs._reset_codes[EMAIL] = entry._replace(
            expires_at=datetime.now(timezone.utc) - timedelta(seconds=1)
        )
        result = prs.verify_code_and_issue_token(EMAIL, code)
        assert result is None

    def test_code_with_whitespace_is_stripped(self):
        code = prs.generate_and_store_code(EMAIL)
        token = prs.verify_code_and_issue_token(EMAIL, f"  {code}  ")
        assert token is not None

    def test_reset_token_expiry_is_approximately_30_minutes(self):
        code = prs.generate_and_store_code(EMAIL)
        token = prs.verify_code_and_issue_token(EMAIL, code)
        _, expires_at = prs._reset_tokens[token]
        diff = expires_at - datetime.now(timezone.utc)
        assert 29 * 60 < diff.total_seconds() <= 30 * 60 + 5


# ── consume_reset_token ───────────────────────────────────────────────────────

class TestConsumeResetToken:
    def _get_token(self) -> str:
        code = prs.generate_and_store_code(EMAIL)
        return prs.verify_code_and_issue_token(EMAIL, code)

    def test_valid_token_returns_email(self):
        token = self._get_token()
        result = prs.consume_reset_token(token)
        assert result == EMAIL

    def test_valid_token_is_single_use(self):
        token = self._get_token()
        prs.consume_reset_token(token)
        second = prs.consume_reset_token(token)
        assert second is None

    def test_consumed_token_is_removed_from_store(self):
        token = self._get_token()
        prs.consume_reset_token(token)
        assert token not in prs._reset_tokens

    def test_invalid_token_returns_none(self):
        result = prs.consume_reset_token("totally-fake-token")
        assert result is None

    def test_expired_token_returns_none(self):
        token = self._get_token()
        email, _ = prs._reset_tokens[token]
        prs._reset_tokens[token] = (email, datetime.now(timezone.utc) - timedelta(seconds=1))
        result = prs.consume_reset_token(token)
        assert result is None

    def test_expired_token_is_removed_from_store(self):
        token = self._get_token()
        email, _ = prs._reset_tokens[token]
        prs._reset_tokens[token] = (email, datetime.now(timezone.utc) - timedelta(seconds=1))
        prs.consume_reset_token(token)
        assert token not in prs._reset_tokens

    def test_returned_email_is_lowercase(self):
        prs.generate_and_store_code("UPPER@HACKATHONFEED.COM")
        code = prs._reset_codes["upper@hackathonfeed.com"].code
        token = prs.verify_code_and_issue_token("upper@hackathonfeed.com", code)
        result = prs.consume_reset_token(token)
        assert result == "upper@hackathonfeed.com"

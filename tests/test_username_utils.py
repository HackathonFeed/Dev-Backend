"""Unit tests for username generation and validation utilities."""
import uuid

import pytest

from app.utils.username_utils import (
    generate_username_candidate,
    is_valid_username,
    normalize_username,
    slugify_username_base,
    validate_username_or_raise,
)

USER_ID = uuid.UUID("947b9870-3e5e-49d1-bc34-3cb3cb9860c7")


# ── normalize_username ────────────────────────────────────────────────────────

class TestNormalizeUsername:
    def test_lowercases_input(self):
        assert normalize_username("Mohamed") == "mohamed"

    def test_strips_whitespace(self):
        assert normalize_username("  hacker  ") == "hacker"

    def test_already_normal(self):
        assert normalize_username("hacker-01") == "hacker-01"


# ── slugify_username_base ─────────────────────────────────────────────────────

class TestSlugifyUsernameBase:
    def test_simple_name(self):
        assert slugify_username_base("Mohamed") == "mohamed"

    def test_name_with_spaces(self):
        result = slugify_username_base("Mohamed Abubakkar")
        assert " " not in result
        assert result == "mohamed-abubakkar"

    def test_special_characters_removed(self):
        result = slugify_username_base("John O'Brien!")
        assert "'" not in result
        assert "!" not in result

    def test_empty_name_becomes_user(self):
        assert slugify_username_base("") == "user"

    def test_result_capped_at_24_chars(self):
        long_name = "a" * 100
        result = slugify_username_base(long_name)
        assert len(result) <= 24

    def test_multiple_spaces_collapse(self):
        result = slugify_username_base("John   Doe")
        assert "--" not in result


# ── is_valid_username ─────────────────────────────────────────────────────────

class TestIsValidUsername:
    def test_valid_simple_username(self):
        assert is_valid_username("hacker01") is True

    def test_valid_with_hyphens_and_underscores(self):
        assert is_valid_username("john-doe_dev") is True

    def test_too_short(self):
        assert is_valid_username("ab") is False

    def test_too_long(self):
        assert is_valid_username("a" * 31) is False

    def test_starts_with_hyphen(self):
        assert is_valid_username("-hacker") is False

    def test_starts_with_underscore(self):
        assert is_valid_username("_hacker") is False

    def test_uppercase_rejected(self):
        assert is_valid_username("HackerDev") is False

    def test_spaces_rejected(self):
        assert is_valid_username("hacker dev") is False

    @pytest.mark.parametrize("reserved", [
        "admin", "api", "auth", "me", "profile", "users", "login", "register",
    ])
    def test_reserved_usernames_rejected(self, reserved: str):
        assert is_valid_username(reserved) is False

    def test_exactly_3_chars_valid(self):
        assert is_valid_username("dev") is True

    def test_exactly_30_chars_valid(self):
        assert is_valid_username("a" * 30) is True

    def test_numbers_only_valid(self):
        assert is_valid_username("123abc") is True


# ── generate_username_candidate ───────────────────────────────────────────────

class TestGenerateUsernameCandidate:
    def test_attempt_0_returns_slug(self):
        result = generate_username_candidate("Mohamed", USER_ID, attempt=0)
        assert result == "mohamed"

    def test_attempt_1_appends_short_id_fragment(self):
        result = generate_username_candidate("Mohamed", USER_ID, attempt=1)
        assert result.startswith("mohamed-")
        assert len(result) > len("mohamed")

    def test_attempt_2_adds_random_hex(self):
        result = generate_username_candidate("Mohamed", USER_ID, attempt=2)
        assert result.startswith("mohamed-")

    def test_result_max_30_chars(self):
        for attempt in range(10):
            result = generate_username_candidate("A Very Long Name Here", USER_ID, attempt)
            assert len(result) <= 30

    def test_result_is_lowercase(self):
        result = generate_username_candidate("UPPER CASE", USER_ID)
        assert result == result.lower()

    def test_different_attempts_differ(self):
        r1 = generate_username_candidate("Mohamed", USER_ID, attempt=0)
        r2 = generate_username_candidate("Mohamed", USER_ID, attempt=1)
        assert r1 != r2


# ── validate_username_or_raise ────────────────────────────────────────────────

class TestValidateUsernameOrRaise:
    def test_valid_username_returns_normalized(self):
        result = validate_username_or_raise("Hacker-01")
        assert result == "hacker-01"

    def test_reserved_username_raises(self):
        with pytest.raises(ValueError, match="Username must be"):
            validate_username_or_raise("admin")

    def test_short_username_raises(self):
        with pytest.raises(ValueError):
            validate_username_or_raise("ab")

    def test_invalid_chars_raises(self):
        with pytest.raises(ValueError):
            validate_username_or_raise("bad username!")

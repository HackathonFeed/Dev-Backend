import pytest
from pydantic import ValidationError

from app.schemas.auth_schema import UserUpdateRequest
from app.utils.social_utils import (
    normalize_github_username,
    normalize_linkedin_username,
    normalize_twitter_username,
    normalize_website,
    parse_github_username,
)

def test_normalize_github_username_from_url():
    assert normalize_github_username("https://github.com/octocat") == "octocat"
    assert normalize_github_username("octocat") == "octocat"


def test_normalize_linkedin_username_from_url():
    assert normalize_linkedin_username("https://linkedin.com/in/mohamed-abubakkar") == "mohamed-abubakkar"
    assert normalize_linkedin_username("mohamed-abubakkar") == "mohamed-abubakkar"


def test_normalize_twitter_username_from_handle_and_url():
    assert normalize_twitter_username("@thahi") == "thahi"
    assert normalize_twitter_username("https://x.com/thahi") == "thahi"
    assert normalize_twitter_username("https://twitter.com/thahi") == "thahi"


def test_normalize_website_from_url_and_domain():
    assert normalize_website("https://portfolio.dev") == "portfolio.dev"
    assert normalize_website("thahi.dev") == "thahi.dev"
    assert normalize_website("https://www.example.com/path") == "example.com/path"


def test_parse_returns_none_for_blank_values():
    assert parse_github_username("") is None
    assert parse_github_username("   ") is None
    assert parse_github_username(None) is None


def test_rejects_full_urls_when_username_expected():
    with pytest.raises(ValueError, match="username only"):
        normalize_github_username("https://github.com/octocat/repo")

    with pytest.raises(ValueError, match="username only"):
        normalize_linkedin_username("https://linkedin.com/company/acme")

    with pytest.raises(ValueError, match="username only"):
        normalize_twitter_username("https://x.com/thahi/status/1")


def test_user_update_request_normalizes_social_fields():
    payload = UserUpdateRequest(
        github_username="https://github.com/octocat",
        linkedin_username="linkedin.com/in/mohamed-abubakkar",
        twitter_username="@thahi",
        website="https://portfolio.dev",
    )
    assert payload.github_username == "octocat"
    assert payload.linkedin_username == "mohamed-abubakkar"
    assert payload.twitter_username == "thahi"
    assert payload.website == "portfolio.dev"


def test_user_update_request_allows_clearing_fields():
    payload = UserUpdateRequest(github_username="", website="")
    assert payload.github_username is None
    assert payload.website is None


def test_user_update_request_rejects_invalid_github():
    with pytest.raises(ValidationError):
        UserUpdateRequest(github_username="bad user name")

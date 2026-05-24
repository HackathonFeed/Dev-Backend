from app.schemas.hackathon_schema import HackathonResponse
from app.utils.text_utils import normalize_hackathon_url


def test_normalize_unstop_duplicated_url():
    raw = (
        "https://unstop.com/https://unstop.com/hackathons/"
        "ideatex-heritage-institute-of-technology-kolkata-1687106"
    )
    expected = (
        "https://unstop.com/hackathons/"
        "ideatex-heritage-institute-of-technology-kolkata-1687106"
    )
    assert normalize_hackathon_url(raw) == expected


def test_normalize_leaves_valid_url_unchanged():
    url = "https://unstop.com/hackathons/sample-hackathon-123"
    assert normalize_hackathon_url(url) == url


def test_normalize_empty_url():
    assert normalize_hackathon_url(None) == ""
    assert normalize_hackathon_url("   ") == ""


def test_hackathon_response_validator_normalizes_url():
    payload = {
        "id": "00000000-0000-0000-0000-000000000001",
        "title": "Sample",
        "organizer": "Org",
        "url": "https://unstop.com/https://unstop.com/hackathons/sample",
        "prize_pool": "TBD",
        "mode": "online",
        "team_size": "1-4",
        "source_platform": "unstop",
    }
    response = HackathonResponse.model_validate(payload)
    assert response.url == "https://unstop.com/hackathons/sample"

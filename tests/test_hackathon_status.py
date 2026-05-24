from datetime import date

from app.core.constants import RegistrationStatus
from app.utils.hackathon_status_utils import derive_registration_status, registration_status_label


def test_derive_status_ended():
    today = date(2026, 5, 24)
    assert (
        derive_registration_status(
            start_date=date(2026, 5, 1),
            end_date=date(2026, 5, 20),
            deadline=date(2026, 5, 10),
            today=today,
        )
        == RegistrationStatus.ENDED
    )


def test_derive_status_registration_closed():
    today = date(2026, 5, 24)
    assert (
        derive_registration_status(
            start_date=date(2026, 5, 20),
            end_date=date(2026, 5, 30),
            deadline=date(2026, 5, 23),
            today=today,
        )
        == RegistrationStatus.CLOSED
    )


def test_derive_status_upcoming():
    today = date(2026, 5, 24)
    assert (
        derive_registration_status(
            start_date=date(2026, 6, 1),
            end_date=date(2026, 6, 3),
            deadline=date(2026, 5, 31),
            today=today,
        )
        == RegistrationStatus.UPCOMING
    )


def test_derive_status_open_live():
    today = date(2026, 5, 24)
    status = derive_registration_status(
        start_date=date(2026, 5, 20),
        end_date=date(2026, 5, 30),
        deadline=date(2026, 5, 28),
        today=today,
    )
    assert status == RegistrationStatus.OPEN
    assert registration_status_label(status, start_date=date(2026, 5, 20), today=today) == "Live Now"


def test_status_labels():
    assert registration_status_label(RegistrationStatus.CLOSED) == "Registration Closed"
    assert registration_status_label(RegistrationStatus.ENDED) == "Ended"

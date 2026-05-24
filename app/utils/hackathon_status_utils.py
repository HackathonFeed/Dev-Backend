from datetime import date

from sqlalchemy import and_, or_

from app.core.constants import RegistrationStatus
from app.models.hackathon_model import Hackathon
from app.utils.date_utils import utc_today


def derive_registration_status(
    *,
    start_date: date | None,
    end_date: date | None,
    deadline: date | None,
    today: date | None = None,
) -> RegistrationStatus:
    """Derive hackathon registration status from event dates."""
    today = today or utc_today()

    if end_date is not None and end_date < today:
        return RegistrationStatus.ENDED

    if deadline is not None and deadline < today:
        return RegistrationStatus.CLOSED

    if start_date is not None and start_date > today:
        return RegistrationStatus.UPCOMING

    return RegistrationStatus.OPEN


def registration_status_label(
    status: RegistrationStatus,
    *,
    start_date: date | None = None,
    today: date | None = None,
) -> str:
    today = today or utc_today()

    if status == RegistrationStatus.ENDED:
        return "Ended"
    if status == RegistrationStatus.CLOSED:
        return "Registration Closed"
    if status == RegistrationStatus.UPCOMING:
        return "Upcoming"
    if start_date is not None and start_date <= today:
        return "Live Now"
    return "Open for Registration"


def is_registration_open(status: RegistrationStatus) -> bool:
    return status in {RegistrationStatus.OPEN, RegistrationStatus.UPCOMING}


def matches_status_filter(
    *,
    start_date: date | None,
    end_date: date | None,
    deadline: date | None,
    only_open: bool,
    status: str | None,
    today: date | None = None,
) -> bool:
    derived = derive_registration_status(
        start_date=start_date,
        end_date=end_date,
        deadline=deadline,
        today=today,
    )

    if status:
        return derived.value == status

    if only_open:
        return is_registration_open(derived)

    return True


def apply_status_date_filters(
    query,
    *,
    today: date | None = None,
    only_open: bool = True,
    status: str | None = None,
):
    today = today or utc_today()

    if status == RegistrationStatus.ENDED.value:
        return query.where(and_(Hackathon.end_date.is_not(None), Hackathon.end_date < today))

    if status == RegistrationStatus.CLOSED.value:
        return query.where(
            and_(
                Hackathon.deadline.is_not(None),
                Hackathon.deadline < today,
                or_(Hackathon.end_date.is_(None), Hackathon.end_date >= today),
            )
        )

    if status == RegistrationStatus.UPCOMING.value:
        return query.where(
            and_(
                Hackathon.start_date.is_not(None),
                Hackathon.start_date > today,
                or_(Hackathon.deadline.is_(None), Hackathon.deadline >= today),
                or_(Hackathon.end_date.is_(None), Hackathon.end_date >= today),
            )
        )

    if status == RegistrationStatus.OPEN.value:
        return query.where(
            and_(
                or_(Hackathon.end_date.is_(None), Hackathon.end_date >= today),
                or_(Hackathon.deadline.is_(None), Hackathon.deadline >= today),
                or_(Hackathon.start_date.is_(None), Hackathon.start_date <= today),
            )
        )

    if only_open:
        return query.where(
            and_(
                or_(Hackathon.end_date.is_(None), Hackathon.end_date >= today),
                or_(Hackathon.deadline.is_(None), Hackathon.deadline >= today),
            )
        )

    return query


def apply_supabase_status_date_filters(
    query,
    *,
    today: date | None = None,
    only_open: bool = True,
    status: str | None = None,
):
    today_iso = (today or utc_today()).isoformat()

    if status == RegistrationStatus.ENDED.value:
        return query.lt("end_date", today_iso)

    if status == RegistrationStatus.CLOSED.value:
        query = query.lt("deadline", today_iso)
        return query.or_(f"end_date.is.null,end_date.gte.{today_iso}")

    if status == RegistrationStatus.UPCOMING.value:
        query = query.gt("start_date", today_iso)
        query = query.or_(f"deadline.is.null,deadline.gte.{today_iso}")
        return query.or_(f"end_date.is.null,end_date.gte.{today_iso}")

    if status == RegistrationStatus.OPEN.value:
        query = query.or_(f"deadline.is.null,deadline.gte.{today_iso}")
        query = query.or_(f"end_date.is.null,end_date.gte.{today_iso}")
        return query.or_(f"start_date.is.null,start_date.lte.{today_iso}")

    if only_open:
        query = query.or_(f"deadline.is.null,deadline.gte.{today_iso}")
        return query.or_(f"end_date.is.null,end_date.gte.{today_iso}")

    return query

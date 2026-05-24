import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tracked_constants import JourneyStepId
from app.models.tracked_project_model import TrackedProjectBundle
from app.repositories.factory import get_tracked_project_repository, get_user_repository
from app.schemas.leaderboard_schema import (
    ActivityDayResponse,
    LeaderboardEntryResponse,
    PublicUserProfileResponse,
    UserHackathonRecordResponse,
    UserHackathonStatsResponse,
)


@dataclass
class _UserAccumulator:
    user_id: uuid.UUID
    name: str
    username: str | None = None
    avatar_url: str | None = None
    participations: int = 0
    submissions: int = 0
    wins: int = 0
    hackathons: list[UserHackathonRecordResponse] = field(default_factory=list)
    activity_counts: dict[str, int] = field(default_factory=dict)


def _step_set(bundle: TrackedProjectBundle) -> set[JourneyStepId]:
    result: set[JourneyStepId] = set()
    for step in bundle.steps:
        step_id = step.step_id
        if isinstance(step_id, JourneyStepId):
            result.add(step_id)
        else:
            result.add(JourneyStepId(step_id))
    return result


def _step_completed_at(bundle: TrackedProjectBundle, step_id: JourneyStepId) -> datetime | None:
    for step in bundle.steps:
        current = step.step_id if isinstance(step.step_id, JourneyStepId) else JourneyStepId(step.step_id)
        if current == step_id:
            return step.completed_at
    return None


def _outcome_from_steps(steps: set[JourneyStepId]) -> str:
    if JourneyStepId.ACCEPTED in steps:
        return "won"
    if JourneyStepId.SUBMITTED in steps:
        return "submitted"
    if JourneyStepId.REGISTERED in steps:
        return "participated"
    return "tracking"


def _date_key(value: datetime) -> str:
    return value.date().isoformat()


def _add_activity_count(acc: _UserAccumulator, value: datetime | None, weight: int = 1) -> None:
    if value is None:
        return
    key = _date_key(value)
    acc.activity_counts[key] = acc.activity_counts.get(key, 0) + weight


def _add_bundle_registration(acc: _UserAccumulator, bundle: TrackedProjectBundle) -> None:
    registered_at = _step_completed_at(bundle, JourneyStepId.REGISTERED)
    if registered_at is not None:
        _add_activity_count(acc, registered_at)


def _activity_response(acc: _UserAccumulator) -> list[ActivityDayResponse]:
    return [
        ActivityDayResponse(date=date, count=count)
        for date, count in sorted(acc.activity_counts.items())
    ]


def _stats_response(acc: _UserAccumulator, user) -> UserHackathonStatsResponse:
    return UserHackathonStatsResponse(
        user=PublicUserProfileResponse.model_validate(user),
        participations=acc.participations,
        submissions=acc.submissions,
        wins=acc.wins,
        hackathons=acc.hackathons,
        activity=_activity_response(acc),
    )


def _hackathon_meta(bundle: TrackedProjectBundle) -> tuple[str, str, str]:
    hackathon = bundle.hackathon
    if hackathon is not None:
        title = getattr(hackathon, "title", None) or bundle.project.title
        prize = getattr(hackathon, "prize_pool", None) or "TBD"
        deadline_raw = getattr(hackathon, "deadline", None)
        deadline = deadline_raw.isoformat() if hasattr(deadline_raw, "isoformat") and deadline_raw else (str(deadline_raw) if deadline_raw else "")
        return title, prize or "TBD", deadline
    return bundle.project.title, "TBD", ""


def _record_from_bundle(bundle: TrackedProjectBundle) -> UserHackathonRecordResponse | None:
    steps = _step_set(bundle)
    if JourneyStepId.REGISTERED not in steps:
        return None

    hackathon_name, prize_pool, deadline = _hackathon_meta(bundle)
    return UserHackathonRecordResponse(
        project_id=bundle.project.id,
        hackathon_id=bundle.project.hackathon_id,
        hackathon_name=hackathon_name,
        prize_pool=prize_pool,
        deadline=deadline,
        stage=bundle.project.stage.value if hasattr(bundle.project.stage, "value") else str(bundle.project.stage),
        outcome=_outcome_from_steps(steps),
        registered_at=_step_completed_at(bundle, JourneyStepId.REGISTERED),
        submitted_at=_step_completed_at(bundle, JourneyStepId.SUBMITTED),
        won_at=_step_completed_at(bundle, JourneyStepId.ACCEPTED),
    )


class LeaderboardService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.projects = get_tracked_project_repository(session)
        self.users = get_user_repository(session)

    async def _load_bundles(self) -> list[TrackedProjectBundle]:
        if hasattr(self.projects, "list_all_bundles"):
            return await self.projects.list_all_bundles()
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Leaderboard is not available for this data layer yet.",
        )

    async def _build_accumulators(self) -> dict[uuid.UUID, _UserAccumulator]:
        bundles = await self._load_bundles()
        grouped: dict[uuid.UUID, list[TrackedProjectBundle]] = defaultdict(list)
        for bundle in bundles:
            grouped[bundle.project.user_id].append(bundle)

        accumulators: dict[uuid.UUID, _UserAccumulator] = {}
        for user_id, user_bundles in grouped.items():
            user = await self.users.get_by_id(user_id)
            if user is None:
                continue

            acc = _UserAccumulator(
                user_id=user_id,
                name=user.name,
                username=user.username,
                avatar_url=user.avatar_url,
            )
            for bundle in user_bundles:
                _add_bundle_registration(acc, bundle)
                record = _record_from_bundle(bundle)
                if record is None:
                    continue
                acc.participations += 1
                if record.outcome in {"submitted", "won"}:
                    acc.submissions += 1
                if record.outcome == "won":
                    acc.wins += 1
                acc.hackathons.append(record)

            if acc.participations > 0 or acc.activity_counts:
                if acc.participations > 0:
                    acc.hackathons.sort(
                        key=lambda item: item.won_at or item.submitted_at or item.registered_at or datetime.min.replace(tzinfo=None),
                        reverse=True,
                    )
                accumulators[user_id] = acc

        return accumulators

    async def get_leaderboard(self, *, limit: int = 50) -> list[LeaderboardEntryResponse]:
        accumulators = await self._build_accumulators()
        ordered = sorted(
            accumulators.values(),
            key=lambda item: (item.wins, item.submissions, item.participations, item.name.lower()),
            reverse=True,
        )

        entries: list[LeaderboardEntryResponse] = []
        for index, acc in enumerate(ordered[:limit], start=1):
            entries.append(
                LeaderboardEntryResponse(
                    user_id=acc.user_id,
                    name=acc.name,
                    username=acc.username,
                    avatar_url=acc.avatar_url,
                    participations=acc.participations,
                    submissions=acc.submissions,
                    wins=acc.wins,
                    rank=index,
                )
            )
        return entries

    async def get_user_stats(self, user_id: uuid.UUID) -> UserHackathonStatsResponse:
        user = await self.users.get_by_id(user_id)
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        accumulators = await self._build_accumulators()
        acc = accumulators.get(user_id)
        if acc is None:
            return UserHackathonStatsResponse(
                user=PublicUserProfileResponse.model_validate(user),
                participations=0,
                submissions=0,
                wins=0,
                hackathons=[],
                activity=[],
            )

        return _stats_response(acc, user)

    async def get_public_profile_by_username(self, username: str) -> UserHackathonStatsResponse:
        user = await self.users.get_by_username(username.lower())
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Public profile not found")
        return await self.get_user_stats(user.id)

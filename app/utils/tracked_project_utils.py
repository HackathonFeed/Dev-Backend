import uuid
from datetime import datetime, timezone

from app.core.tracked_constants import (
    JOURNEY_TIMELINE_TYPES,
    JourneyStepId,
    TimelineEventType,
    TrackedStage,
    derive_stage_from_steps,
    get_step_def,
)
from app.models.tracked_project_model import (
    TrackedProject,
    TrackedProjectBundle,
    TrackedProjectMilestone,
    TrackedProjectStep,
    TrackedProjectTeamMember,
    TrackedProjectTimelineEvent,
)
from app.schemas.hackathon_schema import HackathonResponse
from app.utils.hackathon_mapper import to_hackathon_response
from app.schemas.tracked_project_schema import (
    JourneyStepCompletionResponse,
    MilestoneResponse,
    TimelineEventResponse,
    TrackedProjectResponse,
)


def _format_deadline(value) -> str:
    if value is None:
        return ""
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def bundle_to_response(bundle: TrackedProjectBundle) -> TrackedProjectResponse:
    project = bundle.project
    hackathon = bundle.hackathon or getattr(project, "hackathon", None)

    hackathon_name = hackathon.title if hackathon else "Unknown hackathon"
    prize_pool = hackathon.prize_pool if hackathon else "—"
    deadline = _format_deadline(getattr(hackathon, "deadline", None))

    steps = bundle.steps or list(getattr(project, "steps", []) or [])
    timeline_events = bundle.timeline_events or list(getattr(project, "timeline_events", []) or [])
    milestones = bundle.milestones or list(getattr(project, "milestones", []) or [])
    team_members = bundle.team_members or list(getattr(project, "team_members", []) or [])

    completed_steps = [
        JourneyStepCompletionResponse(
            step_id=step.step_id.value if hasattr(step.step_id, "value") else str(step.step_id),
            completed_at=step.completed_at,
        )
        for step in sorted(steps, key=lambda s: s.completed_at)
    ]

    timeline = [
        TimelineEventResponse(
            id=event.id,
            type=event.event_type.value if hasattr(event.event_type, "value") else str(event.event_type),
            label=event.label,
            description=event.description,
            timestamp=event.occurred_at,
        )
        for event in sorted(timeline_events, key=lambda e: e.occurred_at)
    ]

    stage = project.stage.value if hasattr(project.stage, "value") else str(project.stage)

    hackathon_response = None
    if hackathon is not None:
        try:
            hackathon_response = to_hackathon_response(hackathon)
        except Exception:
            hackathon_response = None

    return TrackedProjectResponse(
        id=project.id,
        title=project.title,
        hackathon_name=hackathon_name,
        hackathon_id=project.hackathon_id,
        prize_pool=prize_pool or "—",
        deadline=deadline,
        stage=stage,
        concept=project.concept,
        milestones=[
            MilestoneResponse(id=m.id, text=m.text, completed=m.completed) for m in milestones
        ],
        team=[member.role_name for member in team_members],
        created_at=project.created_at,
        completed_steps=completed_steps,
        timeline=timeline,
        hackathon=hackathon_response,
    )


def supplemental_timeline_events(
    events: list[TrackedProjectTimelineEvent],
) -> list[TrackedProjectTimelineEvent]:
    return [
        event
        for event in events
        if (event.event_type.value if hasattr(event.event_type, "value") else str(event.event_type))
        not in {t.value for t in JOURNEY_TIMELINE_TYPES}
    ]


def rebuild_journey_timeline_events(
    steps: list[TrackedProjectStep],
    supplemental: list[TrackedProjectTimelineEvent],
) -> list[TrackedProjectTimelineEvent]:
    journey_events: list[TrackedProjectTimelineEvent] = []
    for step in sorted(steps, key=lambda s: s.completed_at):
        step_id = step.step_id.value if hasattr(step.step_id, "value") else str(step.step_id)
        step_def = get_step_def(step_id)
        journey_events.append(
            TrackedProjectTimelineEvent(
                id=uuid.uuid4(),
                project_id=step.project_id,
                event_type=TimelineEventType(step_def["timeline_type"]),
                label=step_def["label"],
                description=step_def["description"],
                occurred_at=step.completed_at,
            )
        )

    combined = journey_events + supplemental
    return sorted(combined, key=lambda e: e.occurred_at)


def make_timeline_event(
    *,
    project_id: uuid.UUID,
    event_type: TimelineEventType,
    label: str,
    description: str | None = None,
    occurred_at: datetime | None = None,
) -> TrackedProjectTimelineEvent:
    return TrackedProjectTimelineEvent(
        id=uuid.uuid4(),
        project_id=project_id,
        event_type=event_type,
        label=label,
        description=description,
        occurred_at=occurred_at or datetime.now(timezone.utc),
    )


def make_step(
    *,
    project_id: uuid.UUID,
    step_id: JourneyStepId,
    completed_at: datetime | None = None,
) -> TrackedProjectStep:
    return TrackedProjectStep(
        id=uuid.uuid4(),
        project_id=project_id,
        step_id=step_id,
        completed_at=completed_at or datetime.now(timezone.utc),
    )


def make_milestone(*, project_id: uuid.UUID, text: str) -> TrackedProjectMilestone:
    return TrackedProjectMilestone(
        id=uuid.uuid4(),
        project_id=project_id,
        text=text,
        completed=False,
    )


def make_team_member(*, project_id: uuid.UUID, role_name: str) -> TrackedProjectTeamMember:
    return TrackedProjectTeamMember(
        id=uuid.uuid4(),
        project_id=project_id,
        role_name=role_name,
    )


def sync_project_stage(project: TrackedProject, steps: list[TrackedProjectStep]) -> None:
    step_ids = [
        step.step_id.value if hasattr(step.step_id, "value") else str(step.step_id)
        for step in sorted(steps, key=lambda s: s.completed_at)
    ]
    project.stage = derive_stage_from_steps(step_ids)

from enum import StrEnum


class JourneyStepId(StrEnum):
    REGISTERED = "registered"
    PROJECT_CREATED = "project_created"
    BUILDING = "building"
    SUBMITTED = "submitted"
    ACCEPTED = "accepted"


class TrackedStage(StrEnum):
    IDEA_BACKLOG = "Idea / Backlog"
    IN_PROGRESS = "In Progress"
    SUBMITTED = "Submitted"
    ACCEPTED_WIN = "Accepted / Win"


class TimelineEventType(StrEnum):
    REGISTERED = "registered"
    BOOKMARKED = "bookmarked"
    PROJECT_CREATED = "project_created"
    BUILDING = "building"
    SUBMITTED = "submitted"
    ACCEPTED = "accepted"
    STAGE_CHANGED = "stage_changed"
    MILESTONE_COMPLETED = "milestone_completed"
    MILESTONE_ADDED = "milestone_added"
    TEAM_MEMBER_ADDED = "team_member_added"
    IDEA_VALIDATED = "idea_validated"
    NOTE = "note"


JOURNEY_STEPS: list[dict[str, str]] = [
    {
        "id": JourneyStepId.REGISTERED,
        "label": "Registered",
        "description": "Signed up for the hackathon.",
        "stage": TrackedStage.IDEA_BACKLOG,
        "timeline_type": TimelineEventType.REGISTERED,
    },
    {
        "id": JourneyStepId.PROJECT_CREATED,
        "label": "Project created",
        "description": "Defined your project name and idea.",
        "stage": TrackedStage.IDEA_BACKLOG,
        "timeline_type": TimelineEventType.PROJECT_CREATED,
    },
    {
        "id": JourneyStepId.BUILDING,
        "label": "Building",
        "description": "Actively developing your prototype.",
        "stage": TrackedStage.IN_PROGRESS,
        "timeline_type": TimelineEventType.BUILDING,
    },
    {
        "id": JourneyStepId.SUBMITTED,
        "label": "Submitted",
        "description": "Sent your final submission to organizers.",
        "stage": TrackedStage.SUBMITTED,
        "timeline_type": TimelineEventType.SUBMITTED,
    },
    {
        "id": JourneyStepId.ACCEPTED,
        "label": "Accepted / won",
        "description": "Received results — accepted or won a prize.",
        "stage": TrackedStage.ACCEPTED_WIN,
        "timeline_type": TimelineEventType.ACCEPTED,
    },
]

JOURNEY_STEP_ORDER: list[JourneyStepId] = [step["id"] for step in JOURNEY_STEPS]

JOURNEY_TIMELINE_TYPES = {step["timeline_type"] for step in JOURNEY_STEPS}

DEFAULT_MILESTONES = [
    "Assemble core stack and initial repository setup",
    "Validate idea with AI or team feedback",
]

DEFAULT_TEAM = ["Lead Builder"]

DEFAULT_CONCEPT = "Track your progress, milestones, and submission for this hackathon."


def get_step_def(step_id: JourneyStepId | str) -> dict[str, str]:
    for step in JOURNEY_STEPS:
        if step["id"] == step_id:
            return step
    raise ValueError(f"Unknown journey step: {step_id}")


def get_next_step_id(completed_step_ids: list[JourneyStepId | str]) -> JourneyStepId | None:
    if len(completed_step_ids) >= len(JOURNEY_STEP_ORDER):
        return None
    return JOURNEY_STEP_ORDER[len(completed_step_ids)]


def derive_stage_from_steps(completed_step_ids: list[JourneyStepId | str]) -> TrackedStage:
    if not completed_step_ids:
        return TrackedStage.IDEA_BACKLOG
    last_step = completed_step_ids[-1]
    return TrackedStage(get_step_def(last_step)["stage"])

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.hackathon_schema import HackathonResponse


class JourneyStepCompletionResponse(BaseModel):
    step_id: str
    completed_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TimelineEventResponse(BaseModel):
    id: uuid.UUID
    type: str
    label: str
    description: str | None = None
    timestamp: datetime

    model_config = ConfigDict(from_attributes=True)


class MilestoneResponse(BaseModel):
    id: uuid.UUID
    text: str
    completed: bool

    model_config = ConfigDict(from_attributes=True)


class TrackedProjectResponse(BaseModel):
    id: uuid.UUID
    title: str
    hackathon_name: str
    hackathon_id: uuid.UUID
    prize_pool: str
    deadline: str
    stage: str
    concept: str
    milestones: list[MilestoneResponse]
    team: list[str]
    created_at: datetime
    completed_steps: list[JourneyStepCompletionResponse]
    timeline: list[TimelineEventResponse]
    hackathon: HackathonResponse | None = None

    model_config = ConfigDict(from_attributes=True)


class TrackedProjectUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    concept: str | None = None


class MilestoneCreateRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=2000)


class NoteCreateRequest(BaseModel):
    note: str = Field(..., min_length=1, max_length=5000)


class TeamMemberCreateRequest(BaseModel):
    role_name: str = Field(..., min_length=1, max_length=255)

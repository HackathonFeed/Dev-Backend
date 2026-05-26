import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class LeaderboardEntryResponse(BaseModel):
    user_id: uuid.UUID
    name: str
    username: str | None = None
    avatar_url: str | None = None
    participations: int
    submissions: int
    wins: int
    rank: int

    model_config = ConfigDict(from_attributes=True)


class PublicUserProfileResponse(BaseModel):
    id: uuid.UUID
    name: str
    username: str
    interests: list[str]
    avatar_url: str | None = None
    github_username: str | None = None
    linkedin_username: str | None = None
    twitter_username: str | None = None
    website: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserHackathonRecordResponse(BaseModel):
    project_id: uuid.UUID
    hackathon_id: uuid.UUID
    hackathon_name: str
    prize_pool: str
    deadline: str
    stage: str
    outcome: str
    registered_at: datetime | None = None
    submitted_at: datetime | None = None
    won_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class ActivityDayResponse(BaseModel):
    date: str
    count: int

    model_config = ConfigDict(from_attributes=True)


class UserHackathonStatsResponse(BaseModel):
    user: PublicUserProfileResponse
    participations: int
    submissions: int
    wins: int
    hackathons: list[UserHackathonRecordResponse]
    activity: list[ActivityDayResponse] = []

    model_config = ConfigDict(from_attributes=True)

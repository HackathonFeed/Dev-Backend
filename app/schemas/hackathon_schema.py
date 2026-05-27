import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.constants import EventMode, HackathonSort, RegistrationStatus
from app.utils.text_utils import normalize_hackathon_url


class HackathonResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    platform_id: str | None = None
    organizer: str
    url: str
    thumbnail: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    deadline: date | None = None
    prize_pool: str
    mode: EventMode
    location: str | None = None
    status: RegistrationStatus | None = None
    status_label: str | None = None
    registrations: int | None = None
    eligibility: list[str] = Field(default_factory=list)
    team_size: str
    categories: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    sponsors: list[str] = Field(default_factory=list)
    source_platform: str
    scraped_at: datetime | None = None

    @field_validator("url")
    @classmethod
    def normalize_url(cls, value: str) -> str:
        return normalize_hackathon_url(value)


class HackathonFilterParams(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    theme: str | None = None
    mode: str | None = None
    platform: str | None = None
    search: str | None = None
    sort: HackathonSort = HackathonSort.DEADLINE
    only_open: bool = True
    status: str | None = None


class ThemeCount(BaseModel):
    theme: str
    count: int


class PlatformCount(BaseModel):
    platform: str
    total_count: int
    open_count: int

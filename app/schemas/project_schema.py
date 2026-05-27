import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class ProjectMemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    username: str
    full_name: str | None = None
    profile_image: str | None = None


class ProjectDescriptionSectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    title: str
    content: str


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    tagline: str | None = None
    url: str
    thumbnail: str | None = None
    description: str | None = None
    description_sections: list[ProjectDescriptionSectionResponse] = []
    hackathon_name: str | None = None
    hackathon_url: str | None = None
    team_members: list[ProjectMemberResponse] = []
    technologies: list[str] = []
    tags: list[str] = []
    platforms: list[str] = []
    likes_count: int | None = None
    views: int | None = None
    github_url: str | None = None
    demo_url: str | None = None
    prize: str | None = None
    prize_description: str | None = None
    is_winner: bool = False
    source_platform: str = "devfolio"
    scraped_at: str | None = None


class ProjectPlatformStats(BaseModel):
    platform: str
    count: int


class ProjectTechnologyStats(BaseModel):
    technology: str
    count: int


class ProjectFilterParams(BaseModel):
    page: int = 1
    page_size: int = 20
    search: str | None = None
    platform: str | None = None
    technology: str | None = None
    is_winner: bool | None = None
    sort: str = "likes"  # likes | views | recent

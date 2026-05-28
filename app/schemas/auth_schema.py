import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.core.constants import SubscriptionPlan, UserRole
from app.utils.social_utils import (
    parse_github_username,
    parse_linkedin_username,
    parse_twitter_username,
    parse_website,
)


class UserRegisterRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)


class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str


class GoogleLoginRequest(BaseModel):
    id_token: str | None = Field(default=None, min_length=10)
    access_token: str | None = Field(default=None, min_length=10)

    @model_validator(mode="after")
    def require_google_token(self):
        if not self.id_token and not self.access_token:
            raise ValueError("A Google token is required")
        return self


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class UserUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=255)
    username: str | None = Field(default=None, min_length=3, max_length=30)
    interests: list[str] | None = None
    avatar_url: str | None = None
    github_username: str | None = None
    linkedin_username: str | None = None
    twitter_username: str | None = None
    website: str | None = None

    @field_validator("github_username", mode="before")
    @classmethod
    def validate_github_username(cls, value):
        if value is None:
            return None
        try:
            return parse_github_username(value)
        except ValueError as exc:
            raise ValueError(str(exc)) from exc

    @field_validator("linkedin_username", mode="before")
    @classmethod
    def validate_linkedin_username(cls, value):
        if value is None:
            return None
        try:
            return parse_linkedin_username(value)
        except ValueError as exc:
            raise ValueError(str(exc)) from exc

    @field_validator("twitter_username", mode="before")
    @classmethod
    def validate_twitter_username(cls, value):
        if value is None:
            return None
        try:
            return parse_twitter_username(value)
        except ValueError as exc:
            raise ValueError(str(exc)) from exc

    @field_validator("website", mode="before")
    @classmethod
    def validate_website(cls, value):
        if value is None:
            return None
        try:
            return parse_website(value)
        except ValueError as exc:
            raise ValueError(str(exc)) from exc


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    username: str
    email: EmailStr
    role: UserRole
    interests: list[str]
    avatar_url: str | None = None
    github_username: str | None = None
    linkedin_username: str | None = None
    twitter_username: str | None = None
    website: str | None = None
    subscription_plan: SubscriptionPlan = SubscriptionPlan.HACKER
    ai_points: int = 50
    plan_expires_at: datetime | None = None
    created_at: datetime

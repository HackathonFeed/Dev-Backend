"""Schemas for admin-only endpoints."""
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, field_validator

from app.core.constants import SubscriptionPlan, UserRole


class AdminUserRow(BaseModel):
    id: str

    @field_validator("id", mode="before")
    @classmethod
    def coerce_uuid(cls, v: Any) -> str:
        return str(v) if isinstance(v, uuid.UUID) else v
    name: str
    username: str
    email: str
    role: UserRole
    subscription_plan: SubscriptionPlan
    ai_points: int
    plan_expires_at: datetime | None
    avatar_url: str | None
    created_at: datetime | None

    model_config = {"from_attributes": True}


class AdminUserListResponse(BaseModel):
    items: list[AdminUserRow]
    total: int
    page: int
    page_size: int
    pages: int


class UpdateRoleRequest(BaseModel):
    role: UserRole


class UpdatePlanRequest(BaseModel):
    plan: SubscriptionPlan

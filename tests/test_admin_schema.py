"""Unit tests for admin Pydantic schemas (UUID coercion, role/plan validation)."""
import uuid
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.core.constants import SubscriptionPlan, UserRole
from app.schemas.admin_schema import (
    AdminUserListResponse,
    AdminUserRow,
    UpdatePlanRequest,
    UpdateRoleRequest,
)

_FIXED_UUID = uuid.UUID("947b9870-3e5e-49d1-bc34-3cb3cb9860c7")
_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _base_row_data(**overrides) -> dict:
    return {
        "id": _FIXED_UUID,
        "name": "Test Hacker",
        "username": "test-hacker",
        "email": "test@hackathonfeed.com",
        "role": UserRole.USER,
        "subscription_plan": SubscriptionPlan.HACKER,
        "ai_points": 50,
        "plan_expires_at": None,
        "avatar_url": None,
        "created_at": _NOW.isoformat(),
        **overrides,
    }


# ── AdminUserRow ──────────────────────────────────────────────────────────────

class TestAdminUserRow:
    def test_uuid_id_coerced_to_string(self):
        row = AdminUserRow.model_validate(_base_row_data())
        assert isinstance(row.id, str)
        assert row.id == str(_FIXED_UUID)

    def test_string_id_accepted_as_is(self):
        row = AdminUserRow.model_validate(_base_row_data(id=str(_FIXED_UUID)))
        assert row.id == str(_FIXED_UUID)

    def test_all_fields_populated(self):
        row = AdminUserRow.model_validate(_base_row_data())
        assert row.name == "Test Hacker"
        assert row.username == "test-hacker"
        assert row.email == "test@hackathonfeed.com"
        assert row.role == UserRole.USER
        assert row.subscription_plan == SubscriptionPlan.HACKER
        assert row.ai_points == 50
        assert row.plan_expires_at is None
        assert row.avatar_url is None

    def test_builder_plan(self):
        row = AdminUserRow.model_validate(
            _base_row_data(subscription_plan=SubscriptionPlan.BUILDER, ai_points=200)
        )
        assert row.subscription_plan == SubscriptionPlan.BUILDER
        assert row.ai_points == 200

    def test_champion_unlimited_points(self):
        row = AdminUserRow.model_validate(
            _base_row_data(subscription_plan=SubscriptionPlan.CHAMPION, ai_points=-1)
        )
        assert row.ai_points == -1

    def test_admin_role(self):
        row = AdminUserRow.model_validate(_base_row_data(role=UserRole.ADMIN))
        assert row.role == UserRole.ADMIN

    def test_missing_required_field_raises(self):
        data = _base_row_data()
        del data["email"]
        with pytest.raises(ValidationError):
            AdminUserRow.model_validate(data)


# ── AdminUserListResponse ─────────────────────────────────────────────────────

class TestAdminUserListResponse:
    def test_valid_response(self):
        row = AdminUserRow.model_validate(_base_row_data())
        response = AdminUserListResponse(
            items=[row], total=1, page=1, page_size=20, pages=1
        )
        assert response.total == 1
        assert len(response.items) == 1

    def test_empty_items(self):
        response = AdminUserListResponse(
            items=[], total=0, page=1, page_size=20, pages=1
        )
        assert response.items == []
        assert response.total == 0

    def test_pagination_fields(self):
        row = AdminUserRow.model_validate(_base_row_data())
        response = AdminUserListResponse(
            items=[row], total=100, page=3, page_size=20, pages=5
        )
        assert response.page == 3
        assert response.pages == 5


# ── UpdateRoleRequest ─────────────────────────────────────────────────────────

class TestUpdateRoleRequest:
    def test_valid_user_role(self):
        req = UpdateRoleRequest(role=UserRole.USER)
        assert req.role == UserRole.USER

    def test_valid_admin_role(self):
        req = UpdateRoleRequest(role="admin")
        assert req.role == UserRole.ADMIN

    def test_valid_moderator_role(self):
        req = UpdateRoleRequest(role="moderator")
        assert req.role == UserRole.MODERATOR

    def test_invalid_role_raises(self):
        with pytest.raises(ValidationError):
            UpdateRoleRequest(role="superuser")


# ── UpdatePlanRequest ─────────────────────────────────────────────────────────

class TestUpdatePlanRequest:
    def test_valid_hacker_plan(self):
        req = UpdatePlanRequest(plan="hacker")
        assert req.plan == SubscriptionPlan.HACKER

    def test_valid_builder_plan(self):
        req = UpdatePlanRequest(plan="builder")
        assert req.plan == SubscriptionPlan.BUILDER

    def test_valid_champion_plan(self):
        req = UpdatePlanRequest(plan="champion")
        assert req.plan == SubscriptionPlan.CHAMPION

    def test_invalid_plan_raises(self):
        with pytest.raises(ValidationError):
            UpdatePlanRequest(plan="premium")

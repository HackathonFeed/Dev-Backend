"""Admin-only management endpoints."""
import math
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth_dependency import require_admin
from app.core.constants import PLAN_POINTS
from app.core.database import get_db
from app.repositories import factory as repository_factory
from app.schemas.admin_schema import (
    AdminUserListResponse,
    AdminUserRow,
    UpdatePlanRequest,
    UpdateRoleRequest,
)
from app.schemas.response_schema import APIResponse
from app.services.analytics_service import AnalyticsService
from app.services.embedding_service import generate_missing_embeddings
from app.services.hackathon_service import HackathonService

router = APIRouter(prefix="/admin", tags=["Admin"])


# ── Stats ─────────────────────────────────────────────────────────────────────

@router.get("/stats", response_model=APIResponse[dict])
async def get_admin_stats(
    _: object = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    service = AnalyticsService(session)
    data = await service.get_dashboard_stats()
    return APIResponse(success=True, message="Admin stats fetched", data=data)


# ── Users ─────────────────────────────────────────────────────────────────────

@router.get("/users", response_model=APIResponse[AdminUserListResponse])
async def list_users(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    search: str = Query(default=""),
    _: object = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Paginated list of all users with optional name/email/username search."""
    repo = repository_factory.get_user_repository(db)
    users, total = await repo.list_all(page=page, page_size=page_size, search=search.strip())
    pages = max(1, math.ceil(total / page_size))
    rows = [AdminUserRow.model_validate(u) for u in users]
    data = AdminUserListResponse(items=rows, total=total, page=page, page_size=page_size, pages=pages)
    return APIResponse(success=True, message="Users fetched", data=data)


@router.get("/users/plan-counts", response_model=APIResponse[dict])
async def plan_counts(
    _: object = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Return count of users per subscription plan."""
    repo = repository_factory.get_user_repository(db)
    data = await repo.count_by_plan()
    return APIResponse(success=True, message="Plan counts fetched", data=data)


@router.patch("/users/{user_id}/role", response_model=APIResponse[AdminUserRow])
async def update_user_role(
    user_id: uuid.UUID,
    payload: UpdateRoleRequest,
    current_admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Change a user's role (user / moderator / admin)."""
    if str(user_id) == str(current_admin.id):
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Cannot change your own role.")
    repo = repository_factory.get_user_repository(db)
    updated = await repo.update_role(user_id, payload.role.value)
    return APIResponse(success=True, message="Role updated", data=AdminUserRow.model_validate(updated))


@router.patch("/users/{user_id}/plan", response_model=APIResponse[AdminUserRow])
async def update_user_plan(
    user_id: uuid.UUID,
    payload: UpdatePlanRequest,
    _: object = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Manually set a user's subscription plan (grants points immediately)."""
    repo = repository_factory.get_user_repository(db)
    points = PLAN_POINTS[payload.plan]
    updated = await repo.update_plan(user_id, payload.plan.value, points)
    return APIResponse(success=True, message="Plan updated", data=AdminUserRow.model_validate(updated))


@router.delete("/users/{user_id}", response_model=APIResponse[None])
async def delete_user(
    user_id: uuid.UUID,
    current_admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Permanently delete a user account."""
    if str(user_id) == str(current_admin.id):
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Cannot delete your own account.")
    repo = repository_factory.get_user_repository(db)
    await repo.delete_by_id(user_id)
    return APIResponse(success=True, message="User deleted", data=None)


# ── Hackathons ────────────────────────────────────────────────────────────────

@router.delete("/hackathon/{hackathon_id}", response_model=APIResponse[None])
async def delete_hackathon(
    hackathon_id: uuid.UUID,
    _: object = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    service = HackathonService(session)
    await service.delete_hackathon(hackathon_id)
    return APIResponse(success=True, message="Hackathon deleted", data=None)


# ── System ────────────────────────────────────────────────────────────────────

@router.post("/scrape", response_model=APIResponse[dict])
async def trigger_scrape(_: object = Depends(require_admin)):
    return APIResponse(
        success=True,
        message="Scrape trigger acknowledged.",
        data={"status": "queued"},
    )


@router.post("/generate-embeddings", response_model=APIResponse[dict])
async def trigger_embedding_generation(
    background_tasks: BackgroundTasks,
    _: object = Depends(require_admin),
):
    """Generate embeddings for un-embedded projects in the background."""
    background_tasks.add_task(generate_missing_embeddings)
    return APIResponse(
        success=True,
        message="Embedding generation started in background.",
        data={"status": "running"},
    )

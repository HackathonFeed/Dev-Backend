import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth_dependency import get_current_user
from app.core.database import get_db
from app.core.tracked_constants import JourneyStepId
from app.schemas.response_schema import APIResponse
from app.schemas.tracked_project_schema import (
    MilestoneCreateRequest,
    NoteCreateRequest,
    TeamMemberCreateRequest,
    TrackedProjectResponse,
    TrackedProjectUpdateRequest,
)
from app.services.tracked_project_service import TrackedProjectService

router = APIRouter(prefix="/tracked-projects", tags=["Tracked Projects"])


@router.get("", response_model=APIResponse[list[TrackedProjectResponse]])
async def list_tracked_projects(
    current_user=Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = TrackedProjectService(session)
    data = await service.list_projects(current_user.id)
    return APIResponse(success=True, message="Tracked projects fetched successfully", data=data)


@router.post("/register/{hackathon_id}", response_model=APIResponse[TrackedProjectResponse])
async def register_hackathon(
    hackathon_id: uuid.UUID,
    current_user=Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = TrackedProjectService(session)
    data = await service.register_hackathon(current_user.id, hackathon_id)
    return APIResponse(success=True, message="Hackathon tracking started", data=data)


@router.get("/{project_id}", response_model=APIResponse[TrackedProjectResponse])
async def get_tracked_project(
    project_id: uuid.UUID,
    current_user=Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = TrackedProjectService(session)
    data = await service.get_project(current_user.id, project_id)
    return APIResponse(success=True, message="Tracked project fetched", data=data)


@router.patch("/{project_id}", response_model=APIResponse[TrackedProjectResponse])
async def update_tracked_project(
    project_id: uuid.UUID,
    payload: TrackedProjectUpdateRequest,
    current_user=Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = TrackedProjectService(session)
    data = await service.update_project(
        current_user.id,
        project_id,
        title=payload.title,
        concept=payload.concept,
    )
    return APIResponse(success=True, message="Tracked project updated successfully", data=data)


@router.delete("/{project_id}", response_model=APIResponse[None])
async def delete_tracked_project(
    project_id: uuid.UUID,
    current_user=Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = TrackedProjectService(session)
    await service.delete_project(current_user.id, project_id)
    return APIResponse(success=True, message="Tracked project removed successfully", data=None)


@router.post("/{project_id}/steps/{step_id}/complete", response_model=APIResponse[TrackedProjectResponse])
async def complete_journey_step(
    project_id: uuid.UUID,
    step_id: JourneyStepId,
    current_user=Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = TrackedProjectService(session)
    data = await service.complete_step(current_user.id, project_id, step_id)
    return APIResponse(success=True, message="Journey step completed", data=data)


@router.post("/{project_id}/steps/undo", response_model=APIResponse[TrackedProjectResponse])
async def undo_journey_step(
    project_id: uuid.UUID,
    current_user=Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = TrackedProjectService(session)
    data = await service.undo_last_step(current_user.id, project_id)
    return APIResponse(success=True, message="Last journey step undone", data=data)


@router.post("/{project_id}/milestones", response_model=APIResponse[TrackedProjectResponse])
async def add_milestone(
    project_id: uuid.UUID,
    payload: MilestoneCreateRequest,
    current_user=Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = TrackedProjectService(session)
    data = await service.add_milestone(current_user.id, project_id, payload.text)
    return APIResponse(success=True, message="Milestone added successfully", data=data)


@router.patch("/{project_id}/milestones/{milestone_id}", response_model=APIResponse[TrackedProjectResponse])
async def toggle_milestone(
    project_id: uuid.UUID,
    milestone_id: uuid.UUID,
    current_user=Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = TrackedProjectService(session)
    data = await service.toggle_milestone(current_user.id, project_id, milestone_id)
    return APIResponse(success=True, message="Milestone updated successfully", data=data)


@router.post("/{project_id}/notes", response_model=APIResponse[TrackedProjectResponse])
async def add_note(
    project_id: uuid.UUID,
    payload: NoteCreateRequest,
    current_user=Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = TrackedProjectService(session)
    data = await service.add_note(current_user.id, project_id, payload.note)
    return APIResponse(success=True, message="Note added successfully", data=data)


@router.post("/{project_id}/team", response_model=APIResponse[TrackedProjectResponse])
async def add_team_member(
    project_id: uuid.UUID,
    payload: TeamMemberCreateRequest,
    current_user=Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = TrackedProjectService(session)
    data = await service.add_team_member(current_user.id, project_id, payload.role_name)
    return APIResponse(success=True, message="Team member added successfully", data=data)

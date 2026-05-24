import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tracked_constants import (
    DEFAULT_CONCEPT,
    DEFAULT_MILESTONES,
    DEFAULT_TEAM,
    JourneyStepId,
    get_next_step_id,
)
from app.repositories.factory import (
    get_analytics_repository,
    get_hackathon_repository,
    get_tracked_project_repository,
)
from app.schemas.tracked_project_schema import TrackedProjectResponse
from app.utils.tracked_project_utils import (
    bundle_to_response,
    make_milestone,
    make_step,
    make_team_member,
    rebuild_journey_timeline_events,
)


class TrackedProjectService:
    def __init__(self, session: AsyncSession):
        self.projects = get_tracked_project_repository(session)
        self.hackathons = get_hackathon_repository(session)
        self.analytics = get_analytics_repository(session)

    async def list_projects(self, user_id: uuid.UUID) -> list[TrackedProjectResponse]:
        bundles = await self.projects.list_by_user(user_id)
        return [bundle_to_response(bundle) for bundle in bundles]

    async def get_project(self, user_id: uuid.UUID, project_id: uuid.UUID) -> TrackedProjectResponse:
        bundle = await self._get_owned_project(user_id, project_id)
        return bundle_to_response(bundle)

    async def register_hackathon(
        self, user_id: uuid.UUID, hackathon_id: uuid.UUID
    ) -> TrackedProjectResponse:
        hackathon = await self.hackathons.get_by_id(hackathon_id)
        if not hackathon:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hackathon not found")

        existing = await self.projects.get_by_user_and_hackathon(user_id, hackathon_id)
        if existing:
            completed_ids = [
                step.step_id.value if hasattr(step.step_id, "value") else str(step.step_id)
                for step in sorted(existing.steps, key=lambda s: s.completed_at)
            ]
            if JourneyStepId.REGISTERED.value not in completed_ids:
                step = make_step(
                    project_id=existing.project.id,
                    step_id=JourneyStepId.REGISTERED,
                )
                existing = await self.projects.add_step(existing, step)
            return bundle_to_response(existing)

        placeholder_id = uuid.uuid4()
        now_step = make_step(project_id=placeholder_id, step_id=JourneyStepId.REGISTERED)
        milestones = [
            make_milestone(project_id=placeholder_id, text=text) for text in DEFAULT_MILESTONES
        ]
        team_members = [
            make_team_member(project_id=placeholder_id, role_name=role) for role in DEFAULT_TEAM
        ]

        bundle = await self.projects.create_project(
            user_id=user_id,
            hackathon_id=hackathon_id,
            title=f"{hackathon.title} entry",
            concept=DEFAULT_CONCEPT,
            steps=[now_step],
            timeline_events=rebuild_journey_timeline_events([now_step], []),
            milestones=milestones,
            team_members=team_members,
        )

        await self.analytics.log_event(
            event_type="track_registered",
            entity_type="hackathon",
            entity_id=str(hackathon_id),
            user_id=user_id,
        )
        return bundle_to_response(bundle)

    async def update_project(
        self,
        user_id: uuid.UUID,
        project_id: uuid.UUID,
        *,
        title: str | None = None,
        concept: str | None = None,
    ) -> TrackedProjectResponse:
        bundle = await self._get_owned_project(user_id, project_id)
        updated = await self.projects.update_project(bundle, title=title, concept=concept)
        return bundle_to_response(updated)

    async def delete_project(self, user_id: uuid.UUID, project_id: uuid.UUID) -> None:
        bundle = await self._get_owned_project(user_id, project_id)
        await self.projects.delete_project(bundle)

    async def complete_step(
        self, user_id: uuid.UUID, project_id: uuid.UUID, step_id: JourneyStepId
    ) -> TrackedProjectResponse:
        bundle = await self._get_owned_project(user_id, project_id)
        completed_ids = [
            step.step_id.value if hasattr(step.step_id, "value") else str(step.step_id)
            for step in sorted(bundle.steps, key=lambda s: s.completed_at)
        ]
        next_step = get_next_step_id(completed_ids)
        if next_step != step_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Next allowed step is {next_step}, not {step_id}",
            )

        step = make_step(project_id=bundle.project.id, step_id=step_id)
        updated = await self.projects.add_step(bundle, step)
        return bundle_to_response(updated)

    async def undo_last_step(self, user_id: uuid.UUID, project_id: uuid.UUID) -> TrackedProjectResponse:
        bundle = await self._get_owned_project(user_id, project_id)
        if not bundle.steps:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No steps to undo")
        updated = await self.projects.undo_last_step(bundle)
        return bundle_to_response(updated)

    async def add_milestone(
        self, user_id: uuid.UUID, project_id: uuid.UUID, text: str
    ) -> TrackedProjectResponse:
        bundle = await self._get_owned_project(user_id, project_id)
        milestone = make_milestone(project_id=bundle.project.id, text=text.strip())
        updated = await self.projects.add_milestone(bundle, milestone)
        return bundle_to_response(updated)

    async def toggle_milestone(
        self, user_id: uuid.UUID, project_id: uuid.UUID, milestone_id: uuid.UUID
    ) -> TrackedProjectResponse:
        bundle = await self._get_owned_project(user_id, project_id)
        if not any(m.id == milestone_id for m in bundle.milestones):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Milestone not found")
        updated = await self.projects.toggle_milestone(bundle, milestone_id)
        return bundle_to_response(updated)

    async def add_note(
        self, user_id: uuid.UUID, project_id: uuid.UUID, note: str
    ) -> TrackedProjectResponse:
        bundle = await self._get_owned_project(user_id, project_id)
        updated = await self.projects.add_note(bundle, note)
        return bundle_to_response(updated)

    async def add_team_member(
        self, user_id: uuid.UUID, project_id: uuid.UUID, role_name: str
    ) -> TrackedProjectResponse:
        bundle = await self._get_owned_project(user_id, project_id)
        member = make_team_member(project_id=bundle.project.id, role_name=role_name.strip())
        updated = await self.projects.add_team_member(bundle, member)
        return bundle_to_response(updated)

    async def _get_owned_project(self, user_id: uuid.UUID, project_id: uuid.UUID):
        bundle = await self.projects.get_by_id(project_id, user_id)
        if not bundle:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tracked project not found")
        return bundle

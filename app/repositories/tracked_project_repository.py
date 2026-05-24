import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.tracked_constants import JourneyStepId, TimelineEventType
from app.models.tracked_project_model import (
    TrackedProject,
    TrackedProjectBundle,
    TrackedProjectMilestone,
    TrackedProjectStep,
    TrackedProjectTeamMember,
    TrackedProjectTimelineEvent,
)
from app.utils.tracked_project_utils import (
    make_timeline_event,
    rebuild_journey_timeline_events,
    supplemental_timeline_events,
    sync_project_stage,
)


def _project_query():
    return select(TrackedProject).options(
        selectinload(TrackedProject.hackathon),
        selectinload(TrackedProject.steps),
        selectinload(TrackedProject.timeline_events),
        selectinload(TrackedProject.milestones),
        selectinload(TrackedProject.team_members),
    )


def _to_bundle(project: TrackedProject) -> TrackedProjectBundle:
    return TrackedProjectBundle(
        project=project,
        hackathon=project.hackathon,
        steps=list(project.steps or []),
        timeline_events=list(project.timeline_events or []),
        milestones=list(project.milestones or []),
        team_members=list(project.team_members or []),
    )


class TrackedProjectRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_by_user(self, user_id: uuid.UUID) -> list[TrackedProjectBundle]:
        result = await self.session.execute(
            _project_query()
            .where(TrackedProject.user_id == user_id)
            .order_by(TrackedProject.updated_at.desc())
        )
        return [_to_bundle(project) for project in result.scalars().all()]

    async def get_by_id(self, project_id: uuid.UUID, user_id: uuid.UUID) -> TrackedProjectBundle | None:
        result = await self.session.execute(
            _project_query().where(
                TrackedProject.id == project_id,
                TrackedProject.user_id == user_id,
            )
        )
        project = result.scalar_one_or_none()
        return _to_bundle(project) if project else None

    async def get_by_user_and_hackathon(
        self, user_id: uuid.UUID, hackathon_id: uuid.UUID
    ) -> TrackedProjectBundle | None:
        result = await self.session.execute(
            _project_query().where(
                TrackedProject.user_id == user_id,
                TrackedProject.hackathon_id == hackathon_id,
            )
        )
        project = result.scalar_one_or_none()
        return _to_bundle(project) if project else None

    async def list_all_bundles(self) -> list[TrackedProjectBundle]:
        result = await self.session.execute(
            _project_query().order_by(TrackedProject.updated_at.desc())
        )
        return [_to_bundle(project) for project in result.scalars().all()]

    async def save_bundle(self, bundle: TrackedProjectBundle) -> TrackedProjectBundle:
        self.session.add(bundle.project)
        for step in bundle.steps:
            self.session.add(step)
        for event in bundle.timeline_events:
            self.session.add(event)
        for milestone in bundle.milestones:
            self.session.add(milestone)
        for member in bundle.team_members:
            self.session.add(member)
        await self.session.flush()
        return await self.get_by_id(bundle.project.id, bundle.project.user_id)  # type: ignore[return-value]

    async def create_project(
        self,
        *,
        user_id: uuid.UUID,
        hackathon_id: uuid.UUID,
        title: str,
        concept: str,
        steps: list[TrackedProjectStep],
        timeline_events: list[TrackedProjectTimelineEvent],
        milestones: list[TrackedProjectMilestone],
        team_members: list[TrackedProjectTeamMember],
    ) -> TrackedProjectBundle:
        project = TrackedProject(
            id=uuid.uuid4(),
            user_id=user_id,
            hackathon_id=hackathon_id,
            title=title,
            concept=concept,
        )
        sync_project_stage(project, steps)
        for step in steps:
            step.project_id = project.id
        for event in timeline_events:
            event.project_id = project.id
        for milestone in milestones:
            milestone.project_id = project.id
        for member in team_members:
            member.project_id = project.id
        bundle = TrackedProjectBundle(
            project=project,
            steps=steps,
            timeline_events=timeline_events,
            milestones=milestones,
            team_members=team_members,
        )
        return await self.save_bundle(bundle)

    async def update_project(
        self,
        bundle: TrackedProjectBundle,
        *,
        title: str | None = None,
        concept: str | None = None,
    ) -> TrackedProjectBundle:
        if title is not None:
            bundle.project.title = title.strip()
        if concept is not None:
            bundle.project.concept = concept.strip()
        bundle.project.updated_at = datetime.now(timezone.utc)
        await self.session.flush()
        refreshed = await self.get_by_id(bundle.project.id, bundle.project.user_id)
        return refreshed  # type: ignore[return-value]

    async def delete_project(self, bundle: TrackedProjectBundle) -> None:
        await self.session.delete(bundle.project)
        await self.session.flush()

    async def replace_timeline(
        self, bundle: TrackedProjectBundle, events: list[TrackedProjectTimelineEvent]
    ) -> None:
        for event in list(bundle.timeline_events):
            await self.session.delete(event)
        bundle.timeline_events = events
        for event in events:
            self.session.add(event)
        await self.session.flush()

    async def add_step(self, bundle: TrackedProjectBundle, step: TrackedProjectStep) -> TrackedProjectBundle:
        bundle.steps.append(step)
        sync_project_stage(bundle.project, bundle.steps)
        bundle.project.updated_at = datetime.now(timezone.utc)
        supplemental = supplemental_timeline_events(bundle.timeline_events)
        rebuilt = rebuild_journey_timeline_events(bundle.steps, supplemental)
        await self.replace_timeline(bundle, rebuilt)
        self.session.add(step)
        await self.session.flush()
        refreshed = await self.get_by_id(bundle.project.id, bundle.project.user_id)
        return refreshed  # type: ignore[return-value]

    async def undo_last_step(self, bundle: TrackedProjectBundle) -> TrackedProjectBundle:
        if not bundle.steps:
            return bundle
        ordered = sorted(bundle.steps, key=lambda s: s.completed_at)
        last_step = ordered[-1]
        bundle.steps = [step for step in bundle.steps if step.id != last_step.id]
        await self.session.delete(last_step)
        sync_project_stage(bundle.project, bundle.steps)
        bundle.project.updated_at = datetime.now(timezone.utc)
        supplemental = supplemental_timeline_events(bundle.timeline_events)
        rebuilt = rebuild_journey_timeline_events(bundle.steps, supplemental)
        await self.replace_timeline(bundle, rebuilt)
        await self.session.flush()
        refreshed = await self.get_by_id(bundle.project.id, bundle.project.user_id)
        return refreshed  # type: ignore[return-value]

    async def add_milestone(
        self, bundle: TrackedProjectBundle, milestone: TrackedProjectMilestone
    ) -> TrackedProjectBundle:
        bundle.milestones.append(milestone)
        event = make_timeline_event(
            project_id=bundle.project.id,
            event_type=TimelineEventType.MILESTONE_ADDED,
            label="Task added",
            description=milestone.text,
        )
        bundle.timeline_events.append(event)
        bundle.project.updated_at = datetime.now(timezone.utc)
        self.session.add(milestone)
        self.session.add(event)
        await self.session.flush()
        refreshed = await self.get_by_id(bundle.project.id, bundle.project.user_id)
        return refreshed  # type: ignore[return-value]

    async def toggle_milestone(
        self, bundle: TrackedProjectBundle, milestone_id: uuid.UUID
    ) -> TrackedProjectBundle:
        milestone = next((m for m in bundle.milestones if m.id == milestone_id), None)
        if milestone is None:
            return bundle
        milestone.completed = not milestone.completed
        if milestone.completed:
            event = make_timeline_event(
                project_id=bundle.project.id,
                event_type=TimelineEventType.MILESTONE_COMPLETED,
                label="Task completed",
                description=milestone.text,
            )
            bundle.timeline_events.append(event)
            self.session.add(event)
        bundle.project.updated_at = datetime.now(timezone.utc)
        await self.session.flush()
        refreshed = await self.get_by_id(bundle.project.id, bundle.project.user_id)
        return refreshed  # type: ignore[return-value]

    async def add_note(self, bundle: TrackedProjectBundle, note: str) -> TrackedProjectBundle:
        event = make_timeline_event(
            project_id=bundle.project.id,
            event_type=TimelineEventType.NOTE,
            label="Note",
            description=note.strip(),
        )
        bundle.timeline_events.append(event)
        bundle.project.updated_at = datetime.now(timezone.utc)
        self.session.add(event)
        await self.session.flush()
        refreshed = await self.get_by_id(bundle.project.id, bundle.project.user_id)
        return refreshed  # type: ignore[return-value]

    async def add_team_member(
        self, bundle: TrackedProjectBundle, member: TrackedProjectTeamMember
    ) -> TrackedProjectBundle:
        bundle.team_members.append(member)
        event = make_timeline_event(
            project_id=bundle.project.id,
            event_type=TimelineEventType.TEAM_MEMBER_ADDED,
            label="Team member added",
            description=member.role_name,
        )
        bundle.timeline_events.append(event)
        bundle.project.updated_at = datetime.now(timezone.utc)
        self.session.add(member)
        self.session.add(event)
        await self.session.flush()
        refreshed = await self.get_by_id(bundle.project.id, bundle.project.user_id)
        return refreshed  # type: ignore[return-value]

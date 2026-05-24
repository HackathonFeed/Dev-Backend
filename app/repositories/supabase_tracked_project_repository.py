import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any

from app.core.tracked_constants import (
    JOURNEY_TIMELINE_TYPES,
    JourneyStepId,
    TimelineEventType,
    TrackedStage,
)
from app.integrations.supabase_client import get_supabase_client
from app.models.tracked_project_model import (
    TrackedProject,
    TrackedProjectBundle,
    TrackedProjectMilestone,
    TrackedProjectStep,
    TrackedProjectTeamMember,
    TrackedProjectTimelineEvent,
)
from app.repositories.supabase_hackathon_repository import _row_to_hackathon
from app.utils.tracked_project_utils import (
    rebuild_journey_timeline_events,
    supplemental_timeline_events,
    sync_project_stage,
)

PROJECT_SELECT = (
    "*, hackathons(*), tracked_project_steps(*), tracked_project_milestones(*), "
    "tracked_project_timeline_events(*), tracked_project_team_members(*)"
)


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _row_to_step(row: dict[str, Any]) -> TrackedProjectStep:
    step = TrackedProjectStep(
        id=uuid.UUID(row["id"]),
        project_id=uuid.UUID(row["project_id"]),
        step_id=JourneyStepId(row["step_id"]),
    )
    step.completed_at = _parse_dt(row.get("completed_at"))
    return step


def _row_to_timeline(row: dict[str, Any]) -> TrackedProjectTimelineEvent:
    event = TrackedProjectTimelineEvent(
        id=uuid.UUID(row["id"]),
        project_id=uuid.UUID(row["project_id"]),
        event_type=TimelineEventType(row["event_type"]),
        label=row["label"],
        description=row.get("description"),
    )
    event.occurred_at = _parse_dt(row.get("occurred_at"))
    return event


def _row_to_milestone(row: dict[str, Any]) -> TrackedProjectMilestone:
    milestone = TrackedProjectMilestone(
        id=uuid.UUID(row["id"]),
        project_id=uuid.UUID(row["project_id"]),
        text=row["text"],
        completed=row.get("completed", False),
    )
    milestone.created_at = _parse_dt(row.get("created_at"))
    return milestone


def _row_to_team_member(row: dict[str, Any]) -> TrackedProjectTeamMember:
    member = TrackedProjectTeamMember(
        id=uuid.UUID(row["id"]),
        project_id=uuid.UUID(row["project_id"]),
        role_name=row["role_name"],
    )
    member.created_at = _parse_dt(row.get("created_at"))
    return member


def _row_to_project(row: dict[str, Any]) -> TrackedProject:
    stage_value = row.get("stage", TrackedStage.IDEA_BACKLOG.value)
    project = TrackedProject(
        id=uuid.UUID(row["id"]),
        user_id=uuid.UUID(row["user_id"]),
        hackathon_id=uuid.UUID(row["hackathon_id"]),
        title=row["title"],
        concept=row.get("concept") or "",
        stage=TrackedStage(stage_value),
    )
    project.created_at = _parse_dt(row.get("created_at"))
    project.updated_at = _parse_dt(row.get("updated_at"))
    return project


def _row_to_bundle(row: dict[str, Any]) -> TrackedProjectBundle:
    project = _row_to_project(row)
    hackathon_row = row.get("hackathons")
    hackathon = _row_to_hackathon(hackathon_row) if hackathon_row else None
    if hackathon:
        project.hackathon = hackathon

    steps = [_row_to_step(item) for item in (row.get("tracked_project_steps") or [])]
    milestones = [_row_to_milestone(item) for item in (row.get("tracked_project_milestones") or [])]
    timeline = [_row_to_timeline(item) for item in (row.get("tracked_project_timeline_events") or [])]
    team = [_row_to_team_member(item) for item in (row.get("tracked_project_team_members") or [])]

    steps.sort(key=lambda s: s.completed_at or datetime.min.replace(tzinfo=timezone.utc))
    timeline.sort(key=lambda e: e.occurred_at or datetime.min.replace(tzinfo=timezone.utc))
    milestones.sort(key=lambda m: m.created_at or datetime.min.replace(tzinfo=timezone.utc))
    team.sort(key=lambda t: t.created_at or datetime.min.replace(tzinfo=timezone.utc))

    return TrackedProjectBundle(
        project=project,
        hackathon=hackathon,
        steps=steps,
        timeline_events=timeline,
        milestones=milestones,
        team_members=team,
    )


class SupabaseTrackedProjectRepository:
    TABLE = "tracked_projects"
    TABLE_STEPS = "tracked_project_steps"
    TABLE_TIMELINE = "tracked_project_timeline_events"
    TABLE_MILESTONES = "tracked_project_milestones"
    TABLE_TEAM = "tracked_project_team_members"

    def __init__(self):
        self.client = get_supabase_client()
        if self.client is None:
            raise RuntimeError("Supabase is not configured")

    async def list_by_user(self, user_id: uuid.UUID) -> list[TrackedProjectBundle]:
        def _fetch():
            response = (
                self.client.table(self.TABLE)
                .select(PROJECT_SELECT)
                .eq("user_id", str(user_id))
                .order("updated_at", desc=True)
                .execute()
            )
            return [_row_to_bundle(row) for row in (response.data or [])]

        return await asyncio.to_thread(_fetch)

    async def list_all_bundles(self) -> list[TrackedProjectBundle]:
        def _fetch():
            response = (
                self.client.table(self.TABLE)
                .select(PROJECT_SELECT)
                .order("updated_at", desc=True)
                .execute()
            )
            return [_row_to_bundle(row) for row in (response.data or [])]

        return await asyncio.to_thread(_fetch)

    async def get_by_id(self, project_id: uuid.UUID, user_id: uuid.UUID) -> TrackedProjectBundle | None:
        def _fetch():
            response = (
                self.client.table(self.TABLE)
                .select(PROJECT_SELECT)
                .eq("id", str(project_id))
                .eq("user_id", str(user_id))
                .limit(1)
                .execute()
            )
            if not response.data:
                return None
            return _row_to_bundle(response.data[0])

        return await asyncio.to_thread(_fetch)

    async def get_by_user_and_hackathon(
        self, user_id: uuid.UUID, hackathon_id: uuid.UUID
    ) -> TrackedProjectBundle | None:
        def _fetch():
            response = (
                self.client.table(self.TABLE)
                .select(PROJECT_SELECT)
                .eq("user_id", str(user_id))
                .eq("hackathon_id", str(hackathon_id))
                .limit(1)
                .execute()
            )
            if not response.data:
                return None
            return _row_to_bundle(response.data[0])

        return await asyncio.to_thread(_fetch)

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

        def _create():
            self.client.table(self.TABLE).insert(
                {
                    "id": str(project.id),
                    "user_id": str(user_id),
                    "hackathon_id": str(hackathon_id),
                    "title": title,
                    "concept": concept,
                    "stage": project.stage.value,
                }
            ).execute()

            if steps:
                self.client.table(self.TABLE_STEPS).insert(
                    [
                        {
                            "id": str(step.id),
                            "project_id": str(project.id),
                            "step_id": step.step_id.value,
                            "completed_at": step.completed_at.isoformat(),
                        }
                        for step in steps
                    ]
                ).execute()

            if timeline_events:
                self.client.table(self.TABLE_TIMELINE).insert(
                    [
                        {
                            "id": str(event.id),
                            "project_id": str(project.id),
                            "event_type": event.event_type.value,
                            "label": event.label,
                            "description": event.description,
                            "occurred_at": event.occurred_at.isoformat(),
                        }
                        for event in timeline_events
                    ]
                ).execute()

            if milestones:
                self.client.table(self.TABLE_MILESTONES).insert(
                    [
                        {
                            "id": str(milestone.id),
                            "project_id": str(project.id),
                            "text": milestone.text,
                            "completed": milestone.completed,
                        }
                        for milestone in milestones
                    ]
                ).execute()

            if team_members:
                self.client.table(self.TABLE_TEAM).insert(
                    [
                        {
                            "id": str(member.id),
                            "project_id": str(project.id),
                            "role_name": member.role_name,
                        }
                        for member in team_members
                    ]
                ).execute()

        await asyncio.to_thread(_create)
        return await self.get_by_id(project.id, user_id)  # type: ignore[return-value]

    async def update_project(
        self,
        bundle: TrackedProjectBundle,
        *,
        title: str | None = None,
        concept: str | None = None,
    ) -> TrackedProjectBundle:
        payload: dict[str, Any] = {"updated_at": datetime.now(timezone.utc).isoformat()}
        if title is not None:
            payload["title"] = title.strip()
        if concept is not None:
            payload["concept"] = concept.strip()

        def _update():
            self.client.table(self.TABLE).update(payload).eq("id", str(bundle.project.id)).execute()

        await asyncio.to_thread(_update)
        return await self.get_by_id(bundle.project.id, bundle.project.user_id)  # type: ignore[return-value]

    async def delete_project(self, bundle: TrackedProjectBundle) -> None:
        def _delete():
            self.client.table(self.TABLE).delete().eq("id", str(bundle.project.id)).execute()

        await asyncio.to_thread(_delete)

    async def _replace_journey_timeline(self, bundle: TrackedProjectBundle) -> None:
        journey_types = {event_type.value for event_type in JOURNEY_TIMELINE_TYPES}
        supplemental = supplemental_timeline_events(bundle.timeline_events)
        rebuilt = rebuild_journey_timeline_events(bundle.steps, supplemental)

        def _sync():
            existing = (
                self.client.table(self.TABLE_TIMELINE)
                .select("id, event_type")
                .eq("project_id", str(bundle.project.id))
                .execute()
            )
            delete_ids = [
                row["id"]
                for row in (existing.data or [])
                if row.get("event_type") in journey_types
            ]
            for event_id in delete_ids:
                self.client.table(self.TABLE_TIMELINE).delete().eq("id", event_id).execute()

            if rebuilt:
                self.client.table(self.TABLE_TIMELINE).insert(
                    [
                        {
                            "id": str(event.id),
                            "project_id": str(bundle.project.id),
                            "event_type": event.event_type.value,
                            "label": event.label,
                            "description": event.description,
                            "occurred_at": event.occurred_at.isoformat(),
                        }
                        for event in rebuilt
                        if (event.event_type.value if hasattr(event.event_type, "value") else str(event.event_type))
                        in journey_types
                    ]
                ).execute()

        await asyncio.to_thread(_sync)

    async def add_step(self, bundle: TrackedProjectBundle, step: TrackedProjectStep) -> TrackedProjectBundle:
        bundle.steps.append(step)
        sync_project_stage(bundle.project, bundle.steps)

        def _insert():
            self.client.table(self.TABLE_STEPS).insert(
                {
                    "id": str(step.id),
                    "project_id": str(bundle.project.id),
                    "step_id": step.step_id.value,
                    "completed_at": step.completed_at.isoformat(),
                }
            ).execute()
            self.client.table(self.TABLE).update(
                {
                    "stage": bundle.project.stage.value,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
            ).eq("id", str(bundle.project.id)).execute()

        await asyncio.to_thread(_insert)
        await self._replace_journey_timeline(bundle)
        return await self.get_by_id(bundle.project.id, bundle.project.user_id)  # type: ignore[return-value]

    async def undo_last_step(self, bundle: TrackedProjectBundle) -> TrackedProjectBundle:
        if not bundle.steps:
            return bundle
        ordered = sorted(bundle.steps, key=lambda s: s.completed_at)
        last_step = ordered[-1]
        bundle.steps = [step for step in bundle.steps if step.id != last_step.id]
        sync_project_stage(bundle.project, bundle.steps)

        def _undo():
            self.client.table(self.TABLE_STEPS).delete().eq("id", str(last_step.id)).execute()
            self.client.table(self.TABLE).update(
                {
                    "stage": bundle.project.stage.value,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
            ).eq("id", str(bundle.project.id)).execute()

        await asyncio.to_thread(_undo)
        await self._replace_journey_timeline(bundle)
        return await self.get_by_id(bundle.project.id, bundle.project.user_id)  # type: ignore[return-value]

    async def add_milestone(
        self, bundle: TrackedProjectBundle, milestone: TrackedProjectMilestone
    ) -> TrackedProjectBundle:
        from app.utils.tracked_project_utils import make_timeline_event

        event = make_timeline_event(
            project_id=bundle.project.id,
            event_type=TimelineEventType.MILESTONE_ADDED,
            label="Task added",
            description=milestone.text,
        )

        def _insert():
            self.client.table(self.TABLE_MILESTONES).insert(
                {
                    "id": str(milestone.id),
                    "project_id": str(bundle.project.id),
                    "text": milestone.text,
                    "completed": milestone.completed,
                }
            ).execute()
            self.client.table(self.TABLE_TIMELINE).insert(
                {
                    "id": str(event.id),
                    "project_id": str(bundle.project.id),
                    "event_type": event.event_type.value,
                    "label": event.label,
                    "description": event.description,
                    "occurred_at": event.occurred_at.isoformat(),
                }
            ).execute()
            self.client.table(self.TABLE).update(
                {"updated_at": datetime.now(timezone.utc).isoformat()}
            ).eq("id", str(bundle.project.id)).execute()

        await asyncio.to_thread(_insert)
        return await self.get_by_id(bundle.project.id, bundle.project.user_id)  # type: ignore[return-value]

    async def toggle_milestone(
        self, bundle: TrackedProjectBundle, milestone_id: uuid.UUID
    ) -> TrackedProjectBundle:
        from app.utils.tracked_project_utils import make_timeline_event

        milestone = next((m for m in bundle.milestones if m.id == milestone_id), None)
        if milestone is None:
            return bundle
        milestone.completed = not milestone.completed

        def _toggle():
            self.client.table(self.TABLE_MILESTONES).update({"completed": milestone.completed}).eq(
                "id", str(milestone_id)
            ).execute()
            if milestone.completed:
                event = make_timeline_event(
                    project_id=bundle.project.id,
                    event_type=TimelineEventType.MILESTONE_COMPLETED,
                    label="Task completed",
                    description=milestone.text,
                )
                self.client.table(self.TABLE_TIMELINE).insert(
                    {
                        "id": str(event.id),
                        "project_id": str(bundle.project.id),
                        "event_type": event.event_type.value,
                        "label": event.label,
                        "description": event.description,
                        "occurred_at": event.occurred_at.isoformat(),
                    }
                ).execute()
            self.client.table(self.TABLE).update(
                {"updated_at": datetime.now(timezone.utc).isoformat()}
            ).eq("id", str(bundle.project.id)).execute()

        await asyncio.to_thread(_toggle)
        return await self.get_by_id(bundle.project.id, bundle.project.user_id)  # type: ignore[return-value]

    async def add_note(self, bundle: TrackedProjectBundle, note: str) -> TrackedProjectBundle:
        from app.utils.tracked_project_utils import make_timeline_event

        event = make_timeline_event(
            project_id=bundle.project.id,
            event_type=TimelineEventType.NOTE,
            label="Note",
            description=note.strip(),
        )

        def _insert():
            self.client.table(self.TABLE_TIMELINE).insert(
                {
                    "id": str(event.id),
                    "project_id": str(bundle.project.id),
                    "event_type": event.event_type.value,
                    "label": event.label,
                    "description": event.description,
                    "occurred_at": event.occurred_at.isoformat(),
                }
            ).execute()
            self.client.table(self.TABLE).update(
                {"updated_at": datetime.now(timezone.utc).isoformat()}
            ).eq("id", str(bundle.project.id)).execute()

        await asyncio.to_thread(_insert)
        return await self.get_by_id(bundle.project.id, bundle.project.user_id)  # type: ignore[return-value]

    async def add_team_member(
        self, bundle: TrackedProjectBundle, member: TrackedProjectTeamMember
    ) -> TrackedProjectBundle:
        from app.utils.tracked_project_utils import make_timeline_event

        event = make_timeline_event(
            project_id=bundle.project.id,
            event_type=TimelineEventType.TEAM_MEMBER_ADDED,
            label="Team member added",
            description=member.role_name,
        )

        def _insert():
            self.client.table(self.TABLE_TEAM).insert(
                {
                    "id": str(member.id),
                    "project_id": str(bundle.project.id),
                    "role_name": member.role_name,
                }
            ).execute()
            self.client.table(self.TABLE_TIMELINE).insert(
                {
                    "id": str(event.id),
                    "project_id": str(bundle.project.id),
                    "event_type": event.event_type.value,
                    "label": event.label,
                    "description": event.description,
                    "occurred_at": event.occurred_at.isoformat(),
                }
            ).execute()
            self.client.table(self.TABLE).update(
                {"updated_at": datetime.now(timezone.utc).isoformat()}
            ).eq("id", str(bundle.project.id)).execute()

        await asyncio.to_thread(_insert)
        return await self.get_by_id(bundle.project.id, bundle.project.user_id)  # type: ignore[return-value]

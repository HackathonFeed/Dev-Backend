import uuid
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.tracked_constants import JourneyStepId, TimelineEventType, TrackedStage


class TrackedProject(Base):
    __tablename__ = "tracked_projects"
    __table_args__ = (
        UniqueConstraint("user_id", "hackathon_id", name="uq_user_hackathon_track"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    hackathon_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("hackathons.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="Untitled project")
    concept: Mapped[str] = mapped_column(Text, nullable=False, default="")
    stage: Mapped[TrackedStage] = mapped_column(
        Enum(TrackedStage, name="tracked_stage", create_type=True),
        default=TrackedStage.IDEA_BACKLOG,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    hackathon = relationship("Hackathon", lazy="joined")
    steps = relationship(
        "TrackedProjectStep",
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="TrackedProjectStep.completed_at",
    )
    timeline_events = relationship(
        "TrackedProjectTimelineEvent",
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="TrackedProjectTimelineEvent.occurred_at",
    )
    milestones = relationship(
        "TrackedProjectMilestone",
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="TrackedProjectMilestone.created_at",
    )
    team_members = relationship(
        "TrackedProjectTeamMember",
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="TrackedProjectTeamMember.created_at",
    )


class TrackedProjectStep(Base):
    __tablename__ = "tracked_project_steps"
    __table_args__ = (
        UniqueConstraint("project_id", "step_id", name="uq_project_step"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tracked_projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    step_id: Mapped[JourneyStepId] = mapped_column(
        Enum(JourneyStepId, name="journey_step_id", create_type=True),
        nullable=False,
    )
    completed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    project = relationship("TrackedProject", back_populates="steps")


class TrackedProjectTimelineEvent(Base):
    __tablename__ = "tracked_project_timeline_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tracked_projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type: Mapped[TimelineEventType] = mapped_column(
        Enum(TimelineEventType, name="timeline_event_type", create_type=True),
        nullable=False,
    )
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    project = relationship("TrackedProject", back_populates="timeline_events")


class TrackedProjectMilestone(Base):
    __tablename__ = "tracked_project_milestones"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tracked_projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    completed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    project = relationship("TrackedProject", back_populates="milestones")


class TrackedProjectTeamMember(Base):
    __tablename__ = "tracked_project_team_members"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tracked_projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role_name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    project = relationship("TrackedProject", back_populates="team_members")


@dataclass
class TrackedProjectBundle:
    project: TrackedProject
    hackathon: object | None = None
    steps: list[TrackedProjectStep] = field(default_factory=list)
    timeline_events: list[TrackedProjectTimelineEvent] = field(default_factory=list)
    milestones: list[TrackedProjectMilestone] = field(default_factory=list)
    team_members: list[TrackedProjectTeamMember] = field(default_factory=list)

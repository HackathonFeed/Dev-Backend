"""Add tracked project tables for per-user hackathon journey tracking."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "002_tracked_projects"
down_revision: Union[str, None] = "001_backend_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    journey_step_id = postgresql.ENUM(
        "registered",
        "project_created",
        "building",
        "submitted",
        "accepted",
        name="journey_step_id",
        create_type=True,
    )
    tracked_stage = postgresql.ENUM(
        "Idea / Backlog",
        "In Progress",
        "Submitted",
        "Accepted / Win",
        name="tracked_stage",
        create_type=True,
    )
    timeline_event_type = postgresql.ENUM(
        "registered",
        "bookmarked",
        "project_created",
        "building",
        "submitted",
        "accepted",
        "stage_changed",
        "milestone_completed",
        "milestone_added",
        "team_member_added",
        "idea_validated",
        "note",
        name="timeline_event_type",
        create_type=True,
    )

    journey_step_id.create(op.get_bind(), checkfirst=True)
    tracked_stage.create(op.get_bind(), checkfirst=True)
    timeline_event_type.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "tracked_projects",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("hackathon_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("hackathons.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False, server_default="Untitled project"),
        sa.Column("concept", sa.Text(), nullable=False, server_default=""),
        sa.Column("stage", tracked_stage, nullable=False, server_default="Idea / Backlog"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("user_id", "hackathon_id", name="uq_user_hackathon_track"),
    )
    op.create_index("ix_tracked_projects_user_id", "tracked_projects", ["user_id"], unique=False)
    op.create_index("ix_tracked_projects_hackathon_id", "tracked_projects", ["hackathon_id"], unique=False)
    op.create_index("ix_tracked_projects_updated_at", "tracked_projects", ["updated_at"], unique=False)

    op.create_table(
        "tracked_project_steps",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tracked_projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("step_id", journey_step_id, nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("project_id", "step_id", name="uq_project_step"),
    )
    op.create_index("ix_tracked_project_steps_project_id", "tracked_project_steps", ["project_id"], unique=False)

    op.create_table(
        "tracked_project_timeline_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tracked_projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", timeline_event_type, nullable=False),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_tracked_timeline_project_id", "tracked_project_timeline_events", ["project_id"], unique=False)
    op.create_index("ix_tracked_timeline_occurred_at", "tracked_project_timeline_events", ["occurred_at"], unique=False)

    op.create_table(
        "tracked_project_milestones",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tracked_projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("completed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_tracked_milestones_project_id", "tracked_project_milestones", ["project_id"], unique=False)

    op.create_table(
        "tracked_project_team_members",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tracked_projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role_name", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_tracked_team_project_id", "tracked_project_team_members", ["project_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_tracked_team_project_id", table_name="tracked_project_team_members")
    op.drop_table("tracked_project_team_members")

    op.drop_index("ix_tracked_milestones_project_id", table_name="tracked_project_milestones")
    op.drop_table("tracked_project_milestones")

    op.drop_index("ix_tracked_timeline_occurred_at", table_name="tracked_project_timeline_events")
    op.drop_index("ix_tracked_timeline_project_id", table_name="tracked_project_timeline_events")
    op.drop_table("tracked_project_timeline_events")

    op.drop_index("ix_tracked_project_steps_project_id", table_name="tracked_project_steps")
    op.drop_table("tracked_project_steps")

    op.drop_index("ix_tracked_projects_updated_at", table_name="tracked_projects")
    op.drop_index("ix_tracked_projects_hackathon_id", table_name="tracked_projects")
    op.drop_index("ix_tracked_projects_user_id", table_name="tracked_projects")
    op.drop_table("tracked_projects")

    op.execute("DROP TYPE IF EXISTS timeline_event_type")
    op.execute("DROP TYPE IF EXISTS tracked_stage")
    op.execute("DROP TYPE IF EXISTS journey_step_id")

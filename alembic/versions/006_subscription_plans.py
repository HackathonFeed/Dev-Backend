"""Add subscription plan and AI points to users."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "006_subscription_plans"
down_revision: Union[str, None] = "005_user_social_handles"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create the enum type first
    subscription_plan_enum = sa.Enum(
        "hacker", "builder", "champion",
        name="subscription_plan",
    )
    subscription_plan_enum.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "users",
        sa.Column(
            "subscription_plan",
            sa.Enum("hacker", "builder", "champion", name="subscription_plan"),
            nullable=False,
            server_default="hacker",
        ),
    )
    op.add_column(
        "users",
        sa.Column("ai_points", sa.Integer(), nullable=False, server_default="50"),
    )
    op.add_column(
        "users",
        sa.Column("plan_expires_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "plan_expires_at")
    op.drop_column("users", "ai_points")
    op.drop_column("users", "subscription_plan")
    op.execute("DROP TYPE IF EXISTS subscription_plan")

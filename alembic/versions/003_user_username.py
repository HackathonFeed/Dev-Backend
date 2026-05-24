"""Add unique username for public profile URLs."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003_user_username"
down_revision: Union[str, None] = "002_tracked_projects"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("username", sa.String(length=30), nullable=True))
    op.execute(
        """
        UPDATE users
        SET username = LEFT(
            COALESCE(NULLIF(REGEXP_REPLACE(LOWER(TRIM(name)), '[^a-z0-9]+', '-', 'g'), ''), 'user')
            || '-' || SUBSTRING(REPLACE(id::text, '-', ''), 1, 6),
            30
        )
        WHERE username IS NULL
        """
    )
    op.alter_column("users", "username", nullable=False)
    op.create_index("ix_users_username", "users", ["username"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_users_username", table_name="users")
    op.drop_column("users", "username")

"""Add social media handles to users."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "005_user_social_handles"
down_revision: Union[str, None] = "004_user_avatar_url"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("github_username", sa.String(length=100), nullable=True))
    op.add_column("users", sa.Column("linkedin_username", sa.String(length=100), nullable=True))
    op.add_column("users", sa.Column("twitter_username", sa.String(length=100), nullable=True))
    op.add_column("users", sa.Column("website", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "website")
    op.drop_column("users", "twitter_username")
    op.drop_column("users", "linkedin_username")
    op.drop_column("users", "github_username")

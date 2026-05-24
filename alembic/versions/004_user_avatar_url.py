"""Add optional avatar_url for profile photos."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004_user_avatar_url"
down_revision: Union[str, None] = "003_user_username"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("avatar_url", sa.String(length=512), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "avatar_url")

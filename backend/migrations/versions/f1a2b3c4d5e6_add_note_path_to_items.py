"""add note_path to items

Revision ID: f1a2b3c4d5e6
Revises: d5e13d1132ea
Create Date: 2026-08-26 07:10:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, Sequence[str], None] = "d5e13d1132ea"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "items", sa.Column("note_path", sa.String(length=1024), nullable=True)
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("items", "note_path")

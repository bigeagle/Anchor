"""add checksum chain to changes, sync_meta, sync_state cursor checksum and halt flag

Revision ID: d5e13d1132ea
Revises: c5046ec2756f
Create Date: 2026-08-23 22:15:44.526350

"""

import hashlib
import json
import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d5e13d1132ea"
down_revision: Union[str, Sequence[str], None] = "c5046ec2756f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _checksum(prev: str, row) -> str:
    """Same chaining as sync_service.compute_checksum (kept self-contained)."""
    canonical = json.dumps(
        {
            "object_type": row["object_type"],
            "object_id": str(row["object_id"]),
            "op": row["op"],
            "payload": row["payload"],
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(f"{prev}|{canonical}".encode()).hexdigest()


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "sync_meta",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("instance_id", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.add_column(
        "changes",
        sa.Column("checksum", sa.String(length=64), server_default="", nullable=False),
    )
    op.add_column(
        "sync_state", sa.Column("last_checksum", sa.String(length=64), nullable=True)
    )
    op.add_column(
        "sync_state", sa.Column("last_error", sa.String(length=64), nullable=True)
    )

    # Backfill the checksum chain for any pre-existing oplog entries.
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            "SELECT seq, object_type, object_id, op, payload FROM changes ORDER BY seq"
        )
    ).mappings()
    rows = list(rows)
    if rows:
        instance_id = str(uuid.uuid4())
        bind.execute(
            sa.text("INSERT INTO sync_meta (id, instance_id) VALUES (1, :iid)"),
            {"iid": instance_id},
        )
        prev = instance_id
        for row in rows:
            row = dict(row)
            if isinstance(row["payload"], str):
                row["payload"] = json.loads(row["payload"])
            prev = _checksum(prev, row)
            bind.execute(
                sa.text("UPDATE changes SET checksum = :cs WHERE seq = :seq"),
                {"cs": prev, "seq": row["seq"]},
            )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("sync_state", "last_error")
    op.drop_column("sync_state", "last_checksum")
    op.drop_column("changes", "checksum")
    op.drop_table("sync_meta")

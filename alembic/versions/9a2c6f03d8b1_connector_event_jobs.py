"""link one connector-processing job to one canonical event

Revision ID: 9a2c6f03d8b1
Revises: 7e21b9a4d012
Create Date: 2026-09-16 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "9a2c6f03d8b1"
down_revision: Union[str, Sequence[str], None] = "7e21b9a4d012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("source_event_id", sa.String(length=36), nullable=True))
    op.create_index("ix_jobs_source_event_id", "jobs", ["source_event_id"])
    op.create_foreign_key(
        "fk_jobs_source_event_id_events",
        "jobs",
        "events",
        ["source_event_id"],
        ["id"],
    )
    op.create_unique_constraint(
        "uq_jobs_connector_source_event",
        "jobs",
        ["team_id", "type", "source_event_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_jobs_connector_source_event", "jobs", type_="unique")
    op.drop_constraint("fk_jobs_source_event_id_events", "jobs", type_="foreignkey")
    op.drop_index("ix_jobs_source_event_id", table_name="jobs")
    op.drop_column("jobs", "source_event_id")

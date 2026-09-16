"""durable processing spine

Revision ID: 7e21b9a4d012
Revises: 3bce51306165
Create Date: 2026-03-27 20:47:46.556916

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7e21b9a4d012'
down_revision: Union[str, Sequence[str], None] = '3bce51306165'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the durable processing spine."""
    op.create_table(
        "events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("team_id", sa.String(length=128), nullable=False),
        sa.Column("type", sa.String(length=64), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("participants", sa.JSON(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("raw", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_events_team_id", "events", ["team_id"])

    op.create_table(
        "commitments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("team_id", sa.String(length=128), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("owner", sa.String(length=255), nullable=True),
        sa.Column("deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_commitments_team_id", "commitments", ["team_id"])

    op.create_table(
        "tasks",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("team_id", sa.String(length=128), nullable=False),
        sa.Column("commitment_id", sa.String(length=36), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("owner", sa.String(length=255), nullable=True),
        sa.Column("inferred_owner", sa.String(length=255), nullable=True),
        sa.Column("inference_confidence", sa.Float(), nullable=True),
        sa.Column("deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("source_ref", sa.String(length=1024), nullable=False),
        sa.Column("source_snippet", sa.Text(), nullable=True),
        sa.Column("inference_trace", sa.Text(), nullable=True),
        sa.Column("dependencies", sa.JSON(), nullable=False),
        sa.Column("duplicate_candidates", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["commitment_id"], ["commitments.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_tasks_confidence"),
    )
    op.create_index("ix_tasks_team_id", "tasks", ["team_id"])
    op.create_index("ix_tasks_commitment_id", "tasks", ["commitment_id"])

    op.create_table(
        "graph_edges",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("team_id", sa.String(length=128), nullable=False),
        sa.Column("source_id", sa.String(length=36), nullable=False),
        sa.Column("target_id", sa.String(length=36), nullable=False),
        sa.Column("relationship_type", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "team_id",
            "source_id",
            "target_id",
            "relationship_type",
            name="uq_graph_edge_relationship",
        ),
    )
    op.create_index("ix_graph_edges_team_id", "graph_edges", ["team_id"])
    op.create_index("ix_graph_edges_source_id", "graph_edges", ["source_id"])
    op.create_index("ix_graph_edges_target_id", "graph_edges", ["target_id"])

    op.create_table(
        "jobs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("team_id", sa.String(length=128), nullable=False),
        sa.Column("type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("filename", sa.String(length=1024), nullable=True),
        sa.Column("file_path", sa.String(length=2048), nullable=True),
        sa.Column("file_type", sa.String(length=32), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("queue_published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("result_event_id", sa.String(length=36), nullable=True),
        sa.Column("result_commitment_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_jobs_team_id", "jobs", ["team_id"])
    op.create_index("ix_jobs_status", "jobs", ["status"])

    op.create_table(
        "review_decisions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("team_id", sa.String(length=128), nullable=False),
        sa.Column("task_id", sa.String(length=36), nullable=False),
        sa.Column("reviewer_id", sa.String(length=128), nullable=False),
        sa.Column("decision", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("task_id", name="uq_review_decisions_task_id"),
        sa.CheckConstraint("decision IN ('approved', 'rejected')", name="ck_review_decision"),
    )
    op.create_index("ix_review_decisions_team_id", "review_decisions", ["team_id"])
    op.create_index("ix_review_decisions_task_id", "review_decisions", ["task_id"])


def downgrade() -> None:
    """Remove the durable processing spine."""
    op.drop_index("ix_review_decisions_task_id", table_name="review_decisions")
    op.drop_index("ix_review_decisions_team_id", table_name="review_decisions")
    op.drop_table("review_decisions")
    op.drop_index("ix_jobs_status", table_name="jobs")
    op.drop_index("ix_jobs_team_id", table_name="jobs")
    op.drop_table("jobs")
    op.drop_index("ix_graph_edges_target_id", table_name="graph_edges")
    op.drop_index("ix_graph_edges_source_id", table_name="graph_edges")
    op.drop_index("ix_graph_edges_team_id", table_name="graph_edges")
    op.drop_table("graph_edges")
    op.drop_index("ix_tasks_commitment_id", table_name="tasks")
    op.drop_index("ix_tasks_team_id", table_name="tasks")
    op.drop_table("tasks")
    op.drop_index("ix_commitments_team_id", table_name="commitments")
    op.drop_table("commitments")
    op.drop_index("ix_events_team_id", table_name="events")
    op.drop_table("events")

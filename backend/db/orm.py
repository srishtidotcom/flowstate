"""Relational persistence models. Domain objects do not import this module."""

from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Float,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base


Base = declarative_base()


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Timestamped:
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)
    deleted_at = Column(DateTime(timezone=True), nullable=True)


class EventRecord(Timestamped, Base):
    __tablename__ = "events"

    id = Column(String(36), primary_key=True)
    team_id = Column(String(128), nullable=False, index=True)
    type = Column(String(64), nullable=False)
    source = Column(String(64), nullable=False)
    content = Column(Text, nullable=False)
    participants = Column(JSON, nullable=False, default=list)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    raw = Column(JSON, nullable=False, default=dict)


class CommitmentRecord(Timestamped, Base):
    __tablename__ = "commitments"

    id = Column(String(36), primary_key=True)
    team_id = Column(String(128), nullable=False, index=True)
    title = Column(String(512), nullable=False)
    description = Column(Text, nullable=False, default="")
    owner = Column(String(255), nullable=True)
    deadline = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(32), nullable=False, default="active")


class TaskRecord(Timestamped, Base):
    __tablename__ = "tasks"

    id = Column(String(36), primary_key=True)
    team_id = Column(String(128), nullable=False, index=True)
    commitment_id = Column(String(36), ForeignKey("commitments.id"), nullable=True, index=True)
    description = Column(Text, nullable=False)
    owner = Column(String(255), nullable=True)
    inferred_owner = Column(String(255), nullable=True)
    inference_confidence = Column(Float, nullable=True)
    deadline = Column(DateTime(timezone=True), nullable=True)
    confidence = Column(Float, nullable=False)
    source_ref = Column(String(1024), nullable=False)
    source_snippet = Column(Text, nullable=True)
    inference_trace = Column(Text, nullable=True)
    dependencies = Column(JSON, nullable=False, default=list)
    duplicate_candidates = Column(JSON, nullable=False, default=list)
    status = Column(String(32), nullable=False, default="pending")


class GraphEdgeRecord(Base):
    __tablename__ = "graph_edges"
    __table_args__ = (
        UniqueConstraint(
            "source_id",
            "target_id",
            "relationship_type",
            name="uq_graph_edge_relationship",
        ),
    )

    id = Column(String(36), primary_key=True)
    team_id = Column(String(128), nullable=False, index=True)
    source_id = Column(String(36), nullable=False, index=True)
    target_id = Column(String(36), nullable=False, index=True)
    relationship_type = Column(String(64), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    deleted_at = Column(DateTime(timezone=True), nullable=True)


class JobRecord(Base):
    __tablename__ = "jobs"

    id = Column(String(36), primary_key=True)
    team_id = Column(String(128), nullable=False, index=True)
    type = Column(String(64), nullable=False)
    status = Column(String(32), nullable=False, index=True, default="queued")
    filename = Column(String(1024), nullable=True)
    file_path = Column(String(2048), nullable=True)
    file_type = Column(String(32), nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)


class ReviewDecisionRecord(Base):
    __tablename__ = "review_decisions"

    id = Column(String(36), primary_key=True)
    task_id = Column(String(36), ForeignKey("tasks.id"), nullable=False, index=True)
    reviewer_id = Column(String(128), nullable=False)
    decision = Column(String(32), nullable=False)
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

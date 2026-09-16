"""Persistence operations. Functions flush but never commit."""

from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from backend.db.orm import (
    CommitmentRecord,
    EventRecord,
    GraphEdgeRecord,
    JobRecord,
    TaskRecord,
)
from backend.models import Commitment, Event, GraphEdge, Job, Task


def add_event(db: Session, event: Event) -> EventRecord:
    record = EventRecord(
        id=event.id,
        team_id=event.team_id,
        type=event.type,
        source=event.source,
        content=event.content,
        participants=event.participants,
        timestamp=event.timestamp,
        raw=event.raw,
        created_at=event.created_at,
        updated_at=event.updated_at,
        deleted_at=event.deleted_at,
    )
    db.add(record)
    db.flush()
    return record


def add_commitment(db: Session, commitment: Commitment) -> CommitmentRecord:
    record = CommitmentRecord(
        id=commitment.id,
        team_id=commitment.team_id,
        title=commitment.title,
        description=commitment.description,
        owner=commitment.owner,
        deadline=commitment.deadline,
        status=commitment.status,
        created_at=commitment.created_at,
        updated_at=commitment.updated_at,
        deleted_at=commitment.deleted_at,
    )
    db.add(record)
    db.flush()
    return record


def add_task(db: Session, task: Task) -> TaskRecord:
    record = TaskRecord(
        id=task.id,
        team_id=task.team_id,
        commitment_id=task.commitment_id,
        description=task.description,
        owner=task.owner,
        inferred_owner=task.inferred_owner,
        inference_confidence=task.inference_confidence,
        deadline=_parse_deadline(task.deadline),
        confidence=task.confidence,
        source_ref=task.source_ref,
        source_snippet=task.source_snippet,
        inference_trace=task.inference_trace,
        dependencies=task.dependencies,
        duplicate_candidates=task.duplicate_candidates,
        status=task.status,
        created_at=task.created_at,
        updated_at=task.updated_at,
        deleted_at=task.deleted_at,
    )
    db.add(record)
    db.flush()
    return record


def add_graph_edges(db: Session, edges: List[GraphEdge]) -> List[GraphEdgeRecord]:
    records = [
        GraphEdgeRecord(
            id=edge.id,
            team_id=edge.team_id,
            source_id=edge.source_id,
            target_id=edge.target_id,
            relationship_type=edge.relationship_type,
            created_at=edge.created_at,
            deleted_at=edge.deleted_at,
        )
        for edge in edges
    ]
    db.add_all(records)
    db.flush()
    return records


def add_job(db: Session, job: Job) -> JobRecord:
    record = JobRecord(
        id=job.id,
        team_id=job.team_id,
        type=job.type,
        status=job.status,
        filename=job.filename,
        file_path=job.file_path,
        file_type=job.file_type,
        error=job.error,
        created_at=job.created_at,
        updated_at=job.updated_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
    )
    db.add(record)
    db.flush()
    return record


def find_job(db: Session, job_id: str) -> Optional[JobRecord]:
    return db.get(JobRecord, job_id)


def job_from_record(record: JobRecord) -> Job:
    return Job(
        id=record.id,
        team_id=record.team_id,
        type=record.type,
        status=record.status,
        filename=record.filename,
        file_path=record.file_path,
        file_type=record.file_type,
        error=record.error,
        created_at=record.created_at,
        updated_at=record.updated_at,
        started_at=record.started_at,
        completed_at=record.completed_at,
    )


def update_job_status(
    db: Session,
    job_id: str,
    status: str,
    error: Optional[str] = None,
) -> Optional[JobRecord]:
    record = find_job(db, job_id)
    if record is None:
        return None

    now = datetime.now(timezone.utc)
    record.status = status
    record.error = error
    record.updated_at = now
    if status == "running" and record.started_at is None:
        record.started_at = now
    if status in {"succeeded", "failed"}:
        record.completed_at = now
    db.flush()
    return record


def claim_queued_job(db: Session, job_id: str) -> bool:
    """Atomically transition one queued job to running."""
    now = datetime.now(timezone.utc)
    statement = (
        update(JobRecord)
        .where(JobRecord.id == job_id, JobRecord.status == "queued")
        .values(status="running", started_at=now, updated_at=now, error=None)
    )
    result = db.execute(statement)
    db.flush()
    return result.rowcount == 1


def get_task_by_id(db: Session, task_id: str, team_id: str) -> Optional[Task]:
    statement = select(TaskRecord).where(
        TaskRecord.id == task_id,
        TaskRecord.team_id == team_id,
        TaskRecord.deleted_at.is_(None),
    )
    record = db.execute(statement).scalar_one_or_none()
    return _task_from_record(record) if record else None


def get_historical_ownership(
    db: Session,
    team_id: str,
    task_description: str,
) -> Optional[str]:
    statement = (
        select(TaskRecord.owner)
        .where(
            TaskRecord.team_id == team_id,
            func.lower(TaskRecord.description) == task_description.lower(),
            TaskRecord.owner.isnot(None),
            TaskRecord.deleted_at.is_(None),
        )
        .order_by(TaskRecord.updated_at.desc())
        .limit(1)
    )
    return db.execute(statement).scalar_one_or_none()


def get_speaker_activity(
    db: Session,
    team_id: str,
    source_ref: str,
) -> Optional[List[dict]]:
    """Speaker frequency will be backed by persisted source events next."""
    return None


def _task_from_record(record: TaskRecord) -> Task:
    return Task(
        id=record.id,
        description=record.description,
        owner=record.owner,
        inferred_owner=record.inferred_owner,
        inference_confidence=record.inference_confidence,
        deadline=record.deadline.isoformat() if record.deadline else None,
        dependencies=record.dependencies or [],
        confidence=record.confidence,
        source_ref=record.source_ref,
        team_id=record.team_id,
        duplicate_candidates=record.duplicate_candidates or [],
        source_snippet=record.source_snippet,
        inference_trace=record.inference_trace,
        commitment_id=record.commitment_id,
        status=record.status,
        created_at=record.created_at,
        updated_at=record.updated_at,
        deleted_at=record.deleted_at,
    )


def _parse_deadline(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed

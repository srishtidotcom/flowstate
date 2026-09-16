"""Persistence operations. Functions flush but never commit."""

from datetime import datetime, timezone
from typing import Iterable, List, Optional

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
        attempt_count=job.attempt_count,
        queue_published_at=job.queue_published_at,
        result_event_id=job.result_event_id,
        result_commitment_id=job.result_commitment_id,
        created_at=job.created_at,
        updated_at=job.updated_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
    )
    db.add(record)
    db.flush()
    return record


def find_job(db: Session, job_id: str, team_id: str) -> Optional[JobRecord]:
    statement = select(JobRecord).where(
        JobRecord.id == job_id,
        JobRecord.team_id == team_id,
    )
    return db.execute(statement).scalar_one_or_none()


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
        attempt_count=record.attempt_count,
        queue_published_at=record.queue_published_at,
        result_event_id=record.result_event_id,
        result_commitment_id=record.result_commitment_id,
        created_at=record.created_at,
        updated_at=record.updated_at,
        started_at=record.started_at,
        completed_at=record.completed_at,
    )


def event_from_record(record: EventRecord) -> Event:
    return Event(
        id=record.id,
        team_id=record.team_id,
        type=record.type,
        source=record.source,
        content=record.content,
        participants=record.participants or [],
        timestamp=record.timestamp,
        raw=record.raw or {},
        created_at=record.created_at,
        updated_at=record.updated_at,
        deleted_at=record.deleted_at,
    )


def commitment_from_record(record: CommitmentRecord) -> Commitment:
    return Commitment(
        id=record.id,
        team_id=record.team_id,
        title=record.title,
        description=record.description,
        owner=record.owner,
        deadline=record.deadline,
        status=record.status,
        created_at=record.created_at,
        updated_at=record.updated_at,
        deleted_at=record.deleted_at,
    )


def graph_edge_from_record(record: GraphEdgeRecord) -> GraphEdge:
    return GraphEdge(
        id=record.id,
        team_id=record.team_id,
        source_id=record.source_id,
        target_id=record.target_id,
        relationship_type=record.relationship_type,
        created_at=record.created_at,
        deleted_at=record.deleted_at,
    )


def update_job_status(
    db: Session,
    job_id: str,
    team_id: str,
    status: str,
    error: Optional[str] = None,
) -> Optional[JobRecord]:
    record = find_job(db, job_id, team_id)
    if record is None:
        return None

    now = datetime.now(timezone.utc)
    record.status = status
    record.error = error
    record.updated_at = now
    if status == "running" and record.started_at is None:
        record.started_at = now
    if status in {"completed", "failed"}:
        record.completed_at = now
    db.flush()
    return record


def claim_queued_job(db: Session, job_id: str, team_id: str) -> bool:
    """Atomically transition one queued job to running."""
    now = datetime.now(timezone.utc)
    statement = (
        update(JobRecord)
        .where(
            JobRecord.id == job_id,
            JobRecord.team_id == team_id,
            JobRecord.status == "queued",
            JobRecord.queue_published_at.isnot(None),
        )
        .values(
            status="running",
            started_at=now,
            updated_at=now,
            error=None,
            attempt_count=JobRecord.attempt_count + 1,
        )
    )
    result = db.execute(statement)
    db.flush()
    return result.rowcount == 1


def mark_job_enqueued(db: Session, job_id: str, team_id: str) -> Optional[JobRecord]:
    record = find_job(db, job_id, team_id)
    if record is None:
        return None
    record.queue_published_at = datetime.now(timezone.utc)
    record.error = None
    db.flush()
    return record


def mark_job_enqueue_failed(
    db: Session,
    job_id: str,
    team_id: str,
    error: str,
) -> Optional[JobRecord]:
    record = find_job(db, job_id, team_id)
    if record is None:
        return None
    record.error = error
    record.updated_at = datetime.now(timezone.utc)
    db.flush()
    return record


def prepare_failed_job_retry(db: Session, job_id: str, team_id: str) -> Optional[JobRecord]:
    record = find_job(db, job_id, team_id)
    if record is None or record.status != "failed":
        return None
    record.status = "queued"
    record.error = None
    record.queue_published_at = None
    record.completed_at = None
    record.updated_at = datetime.now(timezone.utc)
    db.flush()
    return record


def complete_job(
    db: Session,
    job_id: str,
    team_id: str,
    event_id: str,
    commitment_id: str,
) -> Optional[JobRecord]:
    record = update_job_status(db, job_id, team_id, "completed")
    if record is None:
        return None
    record.result_event_id = event_id
    record.result_commitment_id = commitment_id
    db.flush()
    return record


def find_event(db: Session, event_id: str, team_id: str) -> Optional[EventRecord]:
    statement = select(EventRecord).where(
        EventRecord.id == event_id,
        EventRecord.team_id == team_id,
        EventRecord.deleted_at.is_(None),
    )
    return db.execute(statement).scalar_one_or_none()


def find_commitment(
    db: Session,
    commitment_id: str,
    team_id: str,
) -> Optional[CommitmentRecord]:
    statement = select(CommitmentRecord).where(
        CommitmentRecord.id == commitment_id,
        CommitmentRecord.team_id == team_id,
        CommitmentRecord.deleted_at.is_(None),
    )
    return db.execute(statement).scalar_one_or_none()


def list_tasks_for_commitment(
    db: Session,
    commitment_id: str,
    team_id: str,
) -> List[TaskRecord]:
    statement = (
        select(TaskRecord)
        .where(
            TaskRecord.commitment_id == commitment_id,
            TaskRecord.team_id == team_id,
            TaskRecord.deleted_at.is_(None),
        )
        .order_by(TaskRecord.created_at, TaskRecord.id)
    )
    return list(db.execute(statement).scalars())


def list_graph_edges(
    db: Session,
    team_id: str,
    node_ids: Iterable[str],
) -> List[GraphEdgeRecord]:
    ids = list(node_ids)
    if not ids:
        return []
    statement = select(GraphEdgeRecord).where(
        GraphEdgeRecord.team_id == team_id,
        GraphEdgeRecord.deleted_at.is_(None),
        GraphEdgeRecord.source_id.in_(ids),
        GraphEdgeRecord.target_id.in_(ids),
    )
    return list(db.execute(statement).scalars())


def soft_delete_task(db: Session, task_id: str, team_id: str) -> bool:
    statement = (
        update(TaskRecord)
        .where(
            TaskRecord.id == task_id,
            TaskRecord.team_id == team_id,
            TaskRecord.deleted_at.is_(None),
        )
        .values(deleted_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc))
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
    return task_from_record(record) if record else None


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


def task_from_record(record: TaskRecord) -> Task:
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

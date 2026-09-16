"""Upload job registration and queue dispatch."""

import json
from dataclasses import dataclass
from typing import Any, Optional

from backend.db.database import get_db
from backend.db.repositories import (
    add_job,
    claim_queued_job,
    complete_job,
    commitment_from_record,
    event_from_record,
    find_commitment,
    find_event,
    find_job,
    graph_edge_from_record,
    job_from_record,
    mark_job_enqueued,
    mark_job_enqueue_failed,
    prepare_failed_job_retry,
    list_graph_edges,
    list_tasks_for_commitment,
    task_from_record,
    update_job_status,
)
from backend.models import Commitment, Event, GraphEdge, Job, Task


QUEUE_NAME = "flowstate:jobs"
QUEUE_DEDUPE_SET = "flowstate:jobs:published"
ENQUEUE_ONCE_SCRIPT = """
if redis.call('SISMEMBER', KEYS[1], ARGV[1]) == 1 then
  return 0
end
redis.call('LPUSH', KEYS[2], ARGV[2])
redis.call('SADD', KEYS[1], ARGV[1])
return 1
"""


class JobNotCompletedError(RuntimeError):
    pass


@dataclass(frozen=True)
class JobResults:
    job: Job
    event: Event
    commitment: Commitment
    tasks: list[Task]
    edges: list[GraphEdge]


def enqueue_upload_job(job: Job, queue: Any) -> bool:
    """Persist a job and atomically publish it once for this attempt."""
    with get_db() as db:
        existing = find_job(db, job.id, job.team_id)
        if existing is None:
            add_job(db, job)
            attempt_count = job.attempt_count
        else:
            attempt_count = existing.attempt_count
            if existing.type != job.type:
                raise ValueError(f"Job {job.id} already exists with a different type")

    payload = {
        "type": job.type,
        "job_id": job.id,
        "team_id": job.team_id,
        "filename": job.filename,
        "file_path": job.file_path,
        "file_type": job.file_type,
        "attempt": attempt_count + 1,
    }
    delivery_key = f"{job.id}:{attempt_count}"
    try:
        published = _publish_once(queue, delivery_key, json.dumps(payload))
    except Exception as exc:
        with get_db() as db:
            mark_job_enqueue_failed(
                db,
                job.id,
                job.team_id,
                f"Queue dispatch failed: {exc}",
            )
        raise
    with get_db() as db:
        mark_job_enqueued(db, job.id, job.team_id)
    return published


def get_job(job_id: str, team_id: str) -> Optional[Job]:
    with get_db() as db:
        record = find_job(db, job_id, team_id)
        return job_from_record(record) if record else None


def get_job_results(job_id: str, team_id: str) -> Optional[JobResults]:
    with get_db() as db:
        record = find_job(db, job_id, team_id)
        if record is None:
            return None
        job = job_from_record(record)
        if (
            job.status != "completed"
            or not job.result_event_id
            or not job.result_commitment_id
        ):
            raise JobNotCompletedError(f"Job {job_id} is not completed")

        event_record = find_event(db, job.result_event_id, team_id)
        commitment_record = find_commitment(db, job.result_commitment_id, team_id)
        if event_record is None or commitment_record is None:
            raise RuntimeError(f"Completed job {job_id} has missing result records")
        task_records = list_tasks_for_commitment(db, commitment_record.id, team_id)
        node_ids = [event_record.id, commitment_record.id, *(item.id for item in task_records)]
        edge_records = list_graph_edges(db, team_id, node_ids)
        return JobResults(
            job=job,
            event=event_from_record(event_record),
            commitment=commitment_from_record(commitment_record),
            tasks=[task_from_record(item) for item in task_records],
            edges=[graph_edge_from_record(item) for item in edge_records],
        )


def set_job_status(
    job_id: str,
    team_id: str,
    status: str,
    error: Optional[str] = None,
) -> bool:
    with get_db() as db:
        return update_job_status(db, job_id, team_id, status, error) is not None


def claim_job(job_id: str, team_id: str) -> bool:
    with get_db() as db:
        return claim_queued_job(db, job_id, team_id)


def mark_job_completed(
    job_id: str,
    team_id: str,
    event_id: str,
    commitment_id: str,
) -> bool:
    with get_db() as db:
        return complete_job(db, job_id, team_id, event_id, commitment_id) is not None


def retry_failed_job(job_id: str, team_id: str, queue: Any) -> bool:
    with get_db() as db:
        record = prepare_failed_job_retry(db, job_id, team_id)
        if record is None:
            return False
        job = job_from_record(record)
    enqueue_upload_job(job, queue)
    return True


def _publish_once(queue: Any, delivery_key: str, payload: str) -> bool:
    if hasattr(queue, "enqueue_once"):
        return bool(queue.enqueue_once(QUEUE_NAME, delivery_key, payload))
    result = queue.eval(
        ENQUEUE_ONCE_SCRIPT,
        2,
        QUEUE_DEDUPE_SET,
        QUEUE_NAME,
        delivery_key,
        payload,
    )
    return bool(result)

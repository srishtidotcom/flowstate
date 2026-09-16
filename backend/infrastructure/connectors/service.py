"""Database-primary acceptance and at-least-once connector job dispatch."""

import json
from dataclasses import dataclass
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy.exc import IntegrityError

from backend.db.database import get_db
from backend.db.repositories import (
    add_event,
    add_job,
    event_from_record,
    find_event,
    find_job,
    job_from_record,
)
from backend.infrastructure.connectors.connector_adapter import InboundConnectorAdapter
from backend.ingestion.service import enqueue_job
from backend.models import Event, Job


@dataclass(frozen=True)
class ConnectorAcceptance:
    event: Event
    job: Job
    duplicate: bool
    dispatched: bool


def connector_job_id(event_id: str, team_id: str) -> str:
    identity = json.dumps(
        (team_id, "sync_connector", event_id),
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return str(uuid5(NAMESPACE_URL, f"flowstate:job:{identity}"))


def accept_connector_event(
    adapter: InboundConnectorAdapter,
    payload: dict[str, Any],
    queue: Any,
) -> ConnectorAcceptance:
    event = adapter.normalize_event(payload)
    job_id = connector_job_id(event.id, event.team_id)
    job = Job(
        id=job_id,
        type="sync_connector",
        team_id=event.team_id,
        source_event_id=event.id,
    )

    try:
        event, job, duplicate = _persist_acceptance(event, job)
    except IntegrityError:
        # A concurrent delivery can win between lookup and insert. Database
        # uniqueness is authoritative; reload and return its stable records.
        event, job, duplicate = _load_existing_acceptance(event, job)

    dispatched = False
    if not duplicate or (job.status == "queued" and job.queue_published_at is None):
        try:
            dispatched = enqueue_job(job, queue)
        except Exception:
            # The durable Event and Job intentionally remain accepted and inspectable.
            dispatched = False

    return ConnectorAcceptance(
        event=event,
        job=job,
        duplicate=duplicate,
        dispatched=dispatched,
    )


def _persist_acceptance(event: Event, job: Job) -> tuple[Event, Job, bool]:
    with get_db() as db:
        event_record = find_event(db, event.id, event.team_id)
        job_record = find_job(db, job.id, job.team_id)
        if event_record is not None or job_record is not None:
            return _validate_existing(event, job, event_record, job_record)
        add_event(db, event)
        add_job(db, job)
    return event, job, False


def _load_existing_acceptance(event: Event, job: Job) -> tuple[Event, Job, bool]:
    with get_db() as db:
        return _validate_existing(
            event,
            job,
            find_event(db, event.id, event.team_id),
            find_job(db, job.id, job.team_id),
        )


def _validate_existing(event, job, event_record, job_record) -> tuple[Event, Job, bool]:
    if event_record is None or job_record is None:
        raise RuntimeError("Incomplete connector acceptance detected")
    if job_record.type != "sync_connector" or job_record.source_event_id != event.id:
        raise RuntimeError("Connector idempotency key collision")
    return event_from_record(event_record), job_from_record(job_record), True

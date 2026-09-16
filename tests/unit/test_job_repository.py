import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.db.orm import Base
from backend.db.repositories import (
    add_job,
    add_task,
    claim_queued_job,
    find_job,
    get_task_by_id,
    mark_job_enqueued,
    soft_delete_task,
    update_job_status,
)
from backend.models import Job, Task


def test_job_lifecycle_is_persisted():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        job = Job(type="process_upload", team_id="team-alpha", filename="chat.txt")
        add_job(db, job)
        db.commit()

        stored = find_job(db, job.id, "team-alpha")
        assert stored is not None
        assert stored.status == "queued"

        update_job_status(db, job.id, "team-alpha", "running")
        update_job_status(db, job.id, "team-alpha", "completed")
        db.commit()

        stored = find_job(db, job.id, "team-alpha")
        assert stored.status == "completed"
        assert stored.started_at is not None
        assert stored.completed_at is not None


def test_unknown_job_status_update_is_a_noop():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        assert update_job_status(db, "missing", "team-alpha", "failed", "not found") is None


def test_job_can_only_be_claimed_once():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        job = Job(type="process_upload", team_id="team-alpha")
        add_job(db, job)
        mark_job_enqueued(db, job.id, job.team_id)
        db.commit()

        assert claim_queued_job(db, job.id, job.team_id) is True
        assert claim_queued_job(db, job.id, job.team_id) is False


def test_job_and_soft_delete_queries_are_team_scoped():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        job = Job(id="shared", type="process_upload", team_id="team-alpha")
        task = Task(
            id="task-1",
            description="Private task",
            confidence=0.9,
            source_ref="chat.txt:1",
            team_id="team-alpha",
        )
        add_job(db, job)
        add_task(db, task)
        db.commit()

        assert find_job(db, "shared", "team-beta") is None
        assert get_task_by_id(db, "task-1", "team-beta") is None
        assert soft_delete_task(db, "task-1", "team-beta") is False
        assert soft_delete_task(db, "task-1", "team-alpha") is True
        db.commit()
        assert get_task_by_id(db, "task-1", "team-alpha") is None

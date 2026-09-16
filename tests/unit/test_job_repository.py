import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.db.orm import Base
from backend.db.repositories import add_job, claim_queued_job, find_job, update_job_status
from backend.models import Job


def test_job_lifecycle_is_persisted():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        job = Job(type="process_upload", team_id="team-alpha", filename="chat.txt")
        add_job(db, job)
        db.commit()

        stored = find_job(db, job.id)
        assert stored is not None
        assert stored.status == "queued"

        update_job_status(db, job.id, "running")
        update_job_status(db, job.id, "succeeded")
        db.commit()

        stored = find_job(db, job.id)
        assert stored.status == "succeeded"
        assert stored.started_at is not None
        assert stored.completed_at is not None


def test_unknown_job_status_update_is_a_noop():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        assert update_job_status(db, "missing", "failed", "not found") is None


def test_job_can_only_be_claimed_once():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        job = Job(type="process_upload", team_id="team-alpha")
        add_job(db, job)
        db.commit()

        assert claim_queued_job(db, job.id) is True
        assert claim_queued_job(db, job.id) is False

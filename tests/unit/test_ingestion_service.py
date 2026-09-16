import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from backend.db.database import engine
from backend.db.orm import Base
from backend.ingestion.service import (
    claim_job,
    enqueue_upload_job,
    get_job,
    retry_failed_job,
    set_job_status,
)
from backend.models import Job


class RecordingQueue:
    def __init__(self, error=None):
        self.error = error
        self.messages = []
        self.delivery_keys = set()

    def enqueue_once(self, queue_name, delivery_key, payload):
        if self.error:
            raise self.error
        if delivery_key in self.delivery_keys:
            return False
        self.delivery_keys.add(delivery_key)
        self.messages.append((queue_name, payload))
        return True


def setup_module():
    Base.metadata.create_all(engine)


def test_enqueue_upload_job_persists_before_dispatch():
    queue = RecordingQueue()
    job = Job(
        type="process_upload",
        team_id="team-alpha",
        filename="chat.txt",
        file_path="/tmp/chat.txt",
        file_type=".txt",
    )

    enqueue_upload_job(job, queue)

    stored = get_job(job.id, job.team_id)
    assert stored is not None
    assert stored.status == "queued"
    assert queue.messages[0][0] == "flowstate:jobs"
    assert job.id in queue.messages[0][1]
    assert stored.queue_published_at is not None

    assert enqueue_upload_job(job, queue) is False
    assert len(queue.messages) == 1


def test_queue_failure_is_recorded_on_job():
    queue = RecordingQueue(RuntimeError("redis unavailable"))
    job = Job(type="process_upload", team_id="team-alpha")

    try:
        enqueue_upload_job(job, queue)
    except RuntimeError:
        pass
    else:
        raise AssertionError("queue failure should propagate")

    stored = get_job(job.id, job.team_id)
    assert stored is not None
    assert stored.status == "queued"
    assert stored.error == "Queue dispatch failed: redis unavailable"


def test_failed_job_can_be_republished_for_one_new_attempt():
    queue = RecordingQueue()
    job = Job(type="process_upload", team_id="team-retry")
    enqueue_upload_job(job, queue)

    assert claim_job(job.id, job.team_id) is True
    assert set_job_status(job.id, job.team_id, "failed", "temporary failure") is True
    assert retry_failed_job(job.id, job.team_id, queue) is True
    assert len(queue.messages) == 2
    assert claim_job(job.id, job.team_id) is True

    stored = get_job(job.id, job.team_id)
    assert stored is not None
    assert stored.status == "running"
    assert stored.attempt_count == 2

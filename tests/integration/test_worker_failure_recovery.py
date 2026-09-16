from sqlalchemy import func, select
from sqlalchemy.orm import Session

import backend.worker as worker
from backend.db.orm import CommitmentRecord, EventRecord, GraphEdgeRecord, TaskRecord
from backend.extraction.extractor import ExtractedTask
from backend.extraction.extractor import ExtractionError
from backend.ingestion.service import (
    enqueue_upload_job,
    get_job,
    retry_failed_job,
)
from backend.models import Job
from backend.preprocessing.normalizer import Chunk


def test_worker_failure_is_inspectable_and_retry_is_idempotent(
    isolated_db,
    controlled_queue,
):
    job = Job(
        id="job-retry",
        type="process_upload",
        team_id="team-alpha",
        filename="chat.txt",
        file_path="/objects/chat.txt",
        file_type=".txt",
    )
    enqueue_upload_job(job, controlled_queue)
    payload = controlled_queue.pop_job()
    chunk = Chunk(text="Ship the demo", source_ref="chat.txt:1")

    def fake_extract(chunks):
        return [
            ExtractedTask(
                title="Ship the demo",
                owner="Priya",
                deadline="2026-10-01T10:00:00+00:00",
                confidence=0.95,
                dependencies=[],
                source_ref="chat.txt:1",
                source_snippet="Ship the demo",
            )
        ]

    def process(vector_store):
        return lambda queued: worker.process_job(
            queued,
            normalizer=lambda path, file_type: [chunk],
            extractor=fake_extract,
            enricher=lambda task, team_id: task,
            embedder=lambda texts: [[1.0, 2.0]],
            vector_store=vector_store,
        )

    def fail_vector_store(tasks, vectors):
        raise RuntimeError("vector store unavailable")

    try:
        worker.process_queued_job(payload, processor=process(fail_vector_store))
    except RuntimeError as exc:
        assert str(exc) == "vector store unavailable"
    else:
        raise AssertionError("worker failure should propagate")

    failed = get_job(job.id, job.team_id)
    assert failed is not None
    assert failed.status == "failed"
    assert failed.error == "vector store unavailable"

    with Session(isolated_db) as db:
        before = {
            record: db.execute(select(func.count()).select_from(record)).scalar_one()
            for record in (EventRecord, CommitmentRecord, TaskRecord, GraphEdgeRecord)
        }

    assert retry_failed_job(job.id, job.team_id, controlled_queue) is True
    retry_payload = controlled_queue.pop_job()
    stored = []
    worker.process_queued_job(
        retry_payload,
        processor=process(lambda tasks, vectors: stored.extend(zip(tasks, vectors))),
    )

    completed = get_job(job.id, job.team_id)
    assert completed is not None
    assert completed.status == "completed"
    assert completed.attempt_count == 2
    assert len(stored) == 1
    with Session(isolated_db) as db:
        after = {
            record: db.execute(select(func.count()).select_from(record)).scalar_one()
            for record in (EventRecord, CommitmentRecord, TaskRecord, GraphEdgeRecord)
        }
    assert after == before


def test_unknown_job_type_is_persisted_as_failed(isolated_db, controlled_queue):
    job = Job(id="unknown-job", type="mystery", team_id="team-alpha")
    enqueue_upload_job(job, controlled_queue)

    try:
        worker.process_queued_job(controlled_queue.pop_job())
    except ValueError as exc:
        assert "Unsupported job type" in str(exc)
    else:
        raise AssertionError("unknown job type should fail")

    failed = get_job(job.id, job.team_id)
    assert failed is not None
    assert failed.status == "failed"
    assert "Unsupported job type" in failed.error


def test_extraction_failure_persists_no_downstream_activity(
    isolated_db,
    controlled_queue,
):
    job = Job(
        id="extract-failure",
        type="process_upload",
        team_id="team-alpha",
        filename="chat.txt",
        file_path="/objects/chat.txt",
        file_type=".txt",
    )
    enqueue_upload_job(job, controlled_queue)

    def processor(queued):
        return worker.process_job(
            queued,
            normalizer=lambda path, file_type: [
                Chunk(text="Broken extraction", source_ref="chat.txt:1")
            ],
            extractor=lambda chunks: (_ for _ in ()).throw(
                ExtractionError("schema violation")
            ),
            enricher=lambda task, team_id: task,
        )

    try:
        worker.process_queued_job(controlled_queue.pop_job(), processor=processor)
    except ExtractionError as exc:
        assert str(exc) == "schema violation"
    else:
        raise AssertionError("extraction failure should propagate")

    failed = get_job(job.id, job.team_id)
    assert failed is not None
    assert failed.status == "failed"
    with Session(isolated_db) as db:
        for record in (EventRecord, CommitmentRecord, TaskRecord, GraphEdgeRecord):
            assert db.execute(select(func.count()).select_from(record)).scalar_one() == 0

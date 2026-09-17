from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

import backend.ingestion.upload as upload_api
import backend.worker as worker
from backend.db.orm import CommitmentRecord, EventRecord, GraphEdgeRecord, TaskRecord
from backend.extraction.extractor import ExtractedTask
from backend.ingestion.service import get_job


FIXTURE = Path(__file__).parents[1] / "fixtures" / "sample_whatsapp.txt"


def test_upload_to_api_results_pipeline(
    isolated_db,
    controlled_queue,
    api_request,
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(upload_api, "OBJECT_STORE_PATH", str(tmp_path / "objects"))
    upload = api_request(
        "POST",
        "/upload",
        data={"team_id": "team-alpha"},
        files={"file": ("sample_whatsapp.txt", FIXTURE.read_bytes(), "text/plain")},
    )

    assert upload.status_code == 200
    job_id = upload.json()["job_id"]
    queued = get_job(job_id, "team-alpha")
    assert queued is not None
    assert queued.status == "queued"
    assert queued.queue_published_at is not None
    assert len(controlled_queue.messages) == 1

    payload = controlled_queue.pop_job()
    stored_vectors = []

    def fake_extract(chunks):
        assert chunks[0].source_ref == "sample_whatsapp.txt:1"
        return [
            ExtractedTask(
                title="Prepare the demo",
                owner="Priya",
                deadline="2026-10-01T10:00:00+00:00",
                confidence=0.95,
                dependencies=[],
                source_ref=chunks[0].source_ref,
                source_snippet=chunks[0].text,
            ),
            ExtractedTask(
                title="Launch the demo",
                owner=None,
                deadline=None,
                confidence=0.55,
                dependencies=["Prepare the demo"],
                source_ref=chunks[0].source_ref,
                source_snippet=chunks[0].text,
            ),
        ]

    def processor(job):
        return worker.process_job(
            job,
            extractor=fake_extract,
            enricher=lambda task, team_id, reference_datetime: task,
            embedder=lambda texts: [[float(index), 1.0] for index, _ in enumerate(texts)],
            vector_store=lambda tasks, vectors: stored_vectors.extend(zip(tasks, vectors)),
        )

    result = worker.process_queued_job(payload, processor=processor)

    completed = get_job(job_id, "team-alpha")
    assert completed is not None
    assert completed.status == "completed"
    assert completed.attempt_count == 1
    assert completed.result_event_id == result.event.id
    assert len(stored_vectors) == 2
    assert all(task.team_id == "team-alpha" for task, _ in stored_vectors)

    with Session(isolated_db) as db:
        count = lambda record: db.execute(
            select(func.count()).select_from(record)
        ).scalar_one()
        assert count(EventRecord) == 1
        assert count(CommitmentRecord) == 1
        assert count(TaskRecord) == 2
        assert count(GraphEdgeRecord) == 6
        statuses = set(db.execute(select(TaskRecord.status)).scalars())
        assert statuses == {"approved", "pending_review"}

    response = api_request(
        "GET",
        f"/jobs/{job_id}/results",
        params={"team_id": "team-alpha"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["job"]["status"] == "completed"
    assert len(body["tasks"]) == 2
    assert {edge["relationship_type"] for edge in body["edges"]} == {
        "belongs_to",
        "depends_on",
        "inferred_from",
    }

import json
import time

from sqlalchemy import func, select
from sqlalchemy.orm import Session

import backend.worker as worker
from backend.db.orm import CommitmentRecord, EventRecord, GraphEdgeRecord, JobRecord, TaskRecord
from backend.extraction.extractor import ExtractedTask
from backend.ingestion.service import get_job, retry_failed_job
from backend.infrastructure.connectors.security import signature_for_body


SECRET = "integration-test-bridge-secret"


def payload():
    return {
        "connector": "openclaw",
        "channel": "whatsapp",
        "account_id": "account-a",
        "team_id": "team-alpha",
        "sender": "sender-a",
        "conversation_id": "conversation-a",
        "timestamp": "2026-09-16T12:00:00Z",
        "text": "Prepare the demo by Friday",
        "message_id": "message-a",
        "from_me": False,
        "metadata": {"thread_id": None},
        "openclaw_hook": {
            "event": {
                "from": "conversation-a",
                "content": "Prepare the demo by Friday",
                "messageId": "message-a",
                "senderId": "sender-a",
            },
            "context": {
                "channelId": "whatsapp",
                "accountId": "account-a",
                "conversationId": "conversation-a",
            },
        },
    }


def signed_request(api_request, value):
    body = json.dumps(value, separators=(",", ":")).encode()
    timestamp = str(int(time.time()))
    return api_request(
        "POST",
        "/integrations/openclaw/events",
        content=body,
        headers={
            "content-type": "application/json",
            "x-flowstate-timestamp": timestamp,
            "x-flowstate-signature": signature_for_body(SECRET, timestamp, body),
        },
    )


def fake_extract(chunks):
    assert len(chunks) == 1
    assert chunks[0].speaker == "sender-a"
    assert chunks[0].source_ref.startswith("event:")
    return [
        ExtractedTask(
            title="Prepare the demo",
            owner="sender-a",
            deadline="2026-09-18T17:00:00+00:00",
            confidence=0.95,
            dependencies=[],
            source_ref=chunks[0].source_ref,
            source_snippet=chunks[0].text,
        )
    ]


def processor(vector_store):
    return lambda queued: worker.process_connector_job(
        queued,
        extractor=fake_extract,
        enricher=lambda task, team_id, reference_datetime: task,
        embedder=lambda texts: [[1.0, 2.0] for _ in texts],
        vector_store=vector_store,
    )


def counts(engine):
    with Session(engine) as db:
        return {
            record: db.execute(select(func.count()).select_from(record)).scalar_one()
            for record in (EventRecord, JobRecord, CommitmentRecord, TaskRecord, GraphEdgeRecord)
        }


def test_signed_openclaw_hook_reaches_existing_results_api(
    isolated_db, controlled_queue, api_request, monkeypatch
):
    monkeypatch.setenv("FLOWSTATE_BRIDGE_SECRET", SECRET)
    original = payload()
    accepted = signed_request(api_request, original)

    assert accepted.status_code == 202
    assert accepted.json()["status"] == "queued"
    queued = controlled_queue.pop_job()
    assert queued["type"] == "sync_connector"
    assert queued["event_id"] == accepted.json()["event_id"]

    vectors = []
    result = worker.process_queued_job(
        queued,
        processor=processor(lambda tasks, embeddings: vectors.extend(zip(tasks, embeddings))),
    )
    assert result.event.id == accepted.json()["event_id"]
    assert result.event.raw == original
    assert len(vectors) == 1
    assert counts(isolated_db) == {
        EventRecord: 1,
        JobRecord: 1,
        CommitmentRecord: 1,
        TaskRecord: 1,
        GraphEdgeRecord: 3,
    }

    status = api_request(
        "GET", f"/jobs/{accepted.json()['job_id']}", params={"team_id": "team-alpha"}
    )
    results = api_request(
        "GET",
        f"/jobs/{accepted.json()['job_id']}/results",
        params={"team_id": "team-alpha"},
    )
    assert status.status_code == 200
    assert status.json()["status"] == "completed"
    assert results.status_code == 200
    assert results.json()["event"]["source"] == "whatsapp"
    assert results.json()["tasks"][0]["description"] == "Prepare the demo"
    assert {edge["relationship_type"] for edge in results.json()["edges"]} == {
        "belongs_to",
        "inferred_from",
    }


def test_connector_retry_does_not_duplicate_activity(
    isolated_db, controlled_queue, api_request, monkeypatch
):
    monkeypatch.setenv("FLOWSTATE_BRIDGE_SECRET", SECRET)
    accepted = signed_request(api_request, payload())
    queued = controlled_queue.pop_job()

    def fail_vectors(tasks, embeddings):
        raise RuntimeError("vector store unavailable")

    try:
        worker.process_queued_job(queued, processor=processor(fail_vectors))
    except RuntimeError as exc:
        assert str(exc) == "vector store unavailable"
    else:
        raise AssertionError("vector failure should propagate")

    before = counts(isolated_db)
    failed = get_job(accepted.json()["job_id"], "team-alpha")
    assert failed is not None and failed.status == "failed"
    assert retry_failed_job(failed.id, failed.team_id, controlled_queue) is True
    worker.process_queued_job(
        controlled_queue.pop_job(),
        processor=processor(lambda tasks, embeddings: None),
    )

    assert counts(isolated_db) == before
    completed = get_job(failed.id, failed.team_id)
    assert completed is not None
    assert completed.status == "completed"
    assert completed.attempt_count == 2

import json
import time

from sqlalchemy import func, select
from sqlalchemy.orm import Session

import backend.api.integrations as integrations_api
from backend.db.orm import EventRecord, JobRecord
from backend.ingestion.service import get_job
from backend.infrastructure.connectors.security import signature_for_body


SECRET = "unit-test-bridge-secret"


def payload(**overrides):
    value = {
        "connector": "openclaw",
        "channel": "whatsapp",
        "account_id": "account-a",
        "team_id": "team-alpha",
        "sender": "sender-a",
        "conversation_id": "conversation-a",
        "timestamp": "2026-09-16T12:00:00Z",
        "text": "Prepare the demo",
        "message_id": "message-a",
        "from_me": False,
        "openclaw_hook": {"event": {"messageId": "message-a"}},
    }
    value.update(overrides)
    return value


def signed_headers(body, timestamp=None):
    timestamp = timestamp or str(int(time.time()))
    return {
        "content-type": "application/json",
        "x-flowstate-timestamp": timestamp,
        "x-flowstate-signature": signature_for_body(SECRET, timestamp, body),
    }


def post(api_request, value):
    body = json.dumps(value, separators=(",", ":")).encode()
    return api_request(
        "POST",
        "/integrations/openclaw/events",
        content=body,
        headers=signed_headers(body),
    )


def test_duplicate_delivery_creates_one_event_job_and_queue_message(
    isolated_db, controlled_queue, api_request, monkeypatch
):
    monkeypatch.setenv("FLOWSTATE_BRIDGE_SECRET", SECRET)
    first = post(api_request, payload())
    duplicate = post(api_request, payload())

    assert first.status_code == 202
    assert duplicate.status_code == 200
    assert duplicate.json()["duplicate"] is True
    assert duplicate.json()["event_id"] == first.json()["event_id"]
    assert duplicate.json()["job_id"] == first.json()["job_id"]
    assert len(controlled_queue.messages) == 1
    with Session(isolated_db) as db:
        assert db.execute(select(func.count()).select_from(EventRecord)).scalar_one() == 1
        assert db.execute(select(func.count()).select_from(JobRecord)).scalar_one() == 1


def test_cross_team_delivery_is_isolated(
    isolated_db, controlled_queue, api_request, monkeypatch
):
    monkeypatch.setenv("FLOWSTATE_BRIDGE_SECRET", SECRET)
    alpha = post(api_request, payload(team_id="team-alpha"))
    beta = post(api_request, payload(team_id="team-beta"))

    assert alpha.status_code == beta.status_code == 202
    assert alpha.json()["event_id"] != beta.json()["event_id"]
    assert alpha.json()["job_id"] != beta.json()["job_id"]
    assert len(controlled_queue.messages) == 2


def test_redis_failure_leaves_event_and_job_inspectable(
    isolated_db, controlled_queue, api_request, monkeypatch
):
    class FailingQueue:
        def enqueue_once(self, *args):
            raise RuntimeError("redis unavailable")

    monkeypatch.setenv("FLOWSTATE_BRIDGE_SECRET", SECRET)
    monkeypatch.setattr(integrations_api, "r", FailingQueue())
    accepted = post(api_request, payload())

    assert accepted.status_code == 202
    job = get_job(accepted.json()["job_id"], "team-alpha")
    assert job is not None
    assert job.status == "queued"
    assert job.queue_published_at is None
    assert job.error == "Queue dispatch failed: redis unavailable"
    with Session(isolated_db) as db:
        assert db.get(EventRecord, accepted.json()["event_id"]) is not None

    monkeypatch.setattr(integrations_api, "r", controlled_queue)
    recovered = post(api_request, payload())
    assert recovered.status_code == 200
    assert recovered.json()["job_id"] == accepted.json()["job_id"]
    assert len(controlled_queue.messages) == 1
    job = get_job(accepted.json()["job_id"], "team-alpha")
    assert job is not None
    assert job.error is None
    assert job.queue_published_at is not None


def test_malformed_json_and_payload_policies_are_rejected(
    isolated_db, controlled_queue, api_request, monkeypatch
):
    monkeypatch.setenv("FLOWSTATE_BRIDGE_SECRET", SECRET)
    malformed = b"{not-json"
    assert api_request(
        "POST",
        "/integrations/openclaw/events",
        content=malformed,
        headers=signed_headers(malformed),
    ).status_code == 400
    assert post(api_request, payload(from_me=True)).status_code == 422
    assert post(api_request, payload(channel="telegram")).status_code == 422
    assert post(api_request, payload(text="")).status_code == 422


def test_missing_invalid_and_stale_authentication_are_rejected(
    isolated_db, controlled_queue, api_request, monkeypatch
):
    monkeypatch.setenv("FLOWSTATE_BRIDGE_SECRET", SECRET)
    body = json.dumps(payload(), separators=(",", ":")).encode()
    assert api_request(
        "POST", "/integrations/openclaw/events", content=body
    ).status_code == 401
    bad = signed_headers(body)
    bad["x-flowstate-signature"] = "sha256=bad"
    assert api_request(
        "POST", "/integrations/openclaw/events", content=body, headers=bad
    ).status_code == 401
    stale_timestamp = str(int(time.time()) - 301)
    assert api_request(
        "POST",
        "/integrations/openclaw/events",
        content=body,
        headers=signed_headers(body, stale_timestamp),
    ).status_code == 401


def test_ingress_loopback_policy():
    assert integrations_api._is_loopback("127.0.0.1") is True
    assert integrations_api._is_loopback("::1") is True
    assert integrations_api._is_loopback("192.0.2.10") is False
    assert integrations_api._is_loopback("not-an-address") is False

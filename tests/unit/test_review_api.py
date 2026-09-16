from datetime import datetime, timezone

import asyncio

import httpx

import backend.api.review as review_api
from backend.api.main import app
from backend.governance.service import ReviewConflictError, ReviewTaskNotFoundError
from backend.models import ReviewDecision, Task
from backend.governance.service import ReviewOutcome


def request(method, path, **kwargs):
    async def send():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            return await client.request(method, path, **kwargs)

    return asyncio.run(send())


def _task():
    return Task(
        id="task-1",
        team_id="team-alpha",
        description="Review contract",
        confidence=0.5,
        source_ref="chat.txt:3",
        status="pending_review",
    )


def test_review_queue_response_uses_api_schema(monkeypatch):
    monkeypatch.setattr(review_api, "list_review_tasks", lambda team_id: [_task()])

    response = request("GET", "/review/tasks", params={"team_id": "team-alpha"})

    assert response.status_code == 200
    assert response.json()[0]["description"] == "Review contract"
    assert response.json()[0]["status"] == "pending_review"


def test_review_decision_maps_not_found_and_conflict(monkeypatch):
    def not_found(**kwargs):
        raise ReviewTaskNotFoundError()

    monkeypatch.setattr(review_api, "decide_task", not_found)
    response = request(
        "POST",
        "/review/tasks/missing/decision",
        params={"team_id": "team-alpha"},
        json={"reviewer_id": "reviewer-1", "decision": "approved"},
    )
    assert response.status_code == 404

    def conflict(**kwargs):
        raise ReviewConflictError("already final")

    monkeypatch.setattr(review_api, "decide_task", conflict)
    response = request(
        "POST",
        "/review/tasks/task-1/decision",
        params={"team_id": "team-alpha"},
        json={"reviewer_id": "reviewer-1", "decision": "rejected"},
    )
    assert response.status_code == 409


def test_review_decision_validation_and_success(monkeypatch):
    invalid = request(
        "POST",
        "/review/tasks/task-1/decision",
        params={"team_id": "team-alpha"},
        json={"reviewer_id": "reviewer-1", "decision": "maybe"},
    )
    assert invalid.status_code == 422

    task = _task()
    task.status = "approved"
    decision = ReviewDecision(
        id="decision-1",
        team_id="team-alpha",
        task_id=task.id,
        reviewer_id="reviewer-1",
        decision="approved",
        created_at=datetime.now(timezone.utc),
    )
    monkeypatch.setattr(
        review_api,
        "decide_task",
        lambda **kwargs: ReviewOutcome(task=task, decision=decision),
    )
    response = request(
        "POST",
        "/review/tasks/task-1/decision",
        params={"team_id": "team-alpha"},
        json={"reviewer_id": "reviewer-1", "decision": "approved"},
    )
    assert response.status_code == 200
    assert response.json()["task"]["status"] == "approved"

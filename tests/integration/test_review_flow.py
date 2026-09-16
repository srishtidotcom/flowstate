from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.db.orm import ReviewDecisionRecord, TaskRecord
from backend.db.repositories import add_task
from backend.governance.service import execution_candidates
from backend.models import Task


def _insert(engine, task):
    with Session(engine) as db:
        add_task(db, task)
        db.commit()


def _pending(task_id, deadline="2026-10-01T10:00:00+00:00"):
    return Task(
        id=task_id,
        team_id="team-alpha",
        description=f"Review {task_id}",
        confidence=0.5,
        source_ref="chat.txt:1",
        status="pending_review",
        deadline=deadline,
    )


def test_review_state_transitions_are_durable_and_final(
    isolated_db,
    api_request,
):
    _insert(isolated_db, _pending("approve-me"))
    _insert(isolated_db, _pending("reject-me"))

    queue = api_request("GET", "/review/tasks", params={"team_id": "team-alpha"})
    assert queue.status_code == 200
    assert {task["id"] for task in queue.json()} == {"approve-me", "reject-me"}

    approved = api_request(
        "POST",
        "/review/tasks/approve-me/decision",
        params={"team_id": "team-alpha"},
        json={
            "reviewer_id": "reviewer-1",
            "decision": "approved",
            "reason": "Verified against source",
        },
    )
    rejected = api_request(
        "POST",
        "/review/tasks/reject-me/decision",
        params={"team_id": "team-alpha"},
        json={"reviewer_id": "reviewer-1", "decision": "rejected"},
    )
    assert approved.status_code == 200
    assert rejected.status_code == 200

    duplicate = api_request(
        "POST",
        "/review/tasks/approve-me/decision",
        params={"team_id": "team-alpha"},
        json={"reviewer_id": "reviewer-2", "decision": "rejected"},
    )
    invalid = api_request(
        "POST",
        "/review/tasks/reject-me/decision",
        params={"team_id": "team-alpha"},
        json={"reviewer_id": "reviewer-2", "decision": "maybe"},
    )
    assert duplicate.status_code == 409
    assert invalid.status_code == 422

    with Session(isolated_db) as db:
        statuses = dict(db.execute(select(TaskRecord.id, TaskRecord.status)).all())
        decisions = db.execute(
            select(func.count()).select_from(ReviewDecisionRecord)
        ).scalar_one()
        assert statuses == {"approve-me": "approved", "reject-me": "rejected"}
        assert decisions == 2

    assert [task.id for task in execution_candidates("team-alpha")] == ["approve-me"]

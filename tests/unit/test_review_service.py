import os
from contextlib import contextmanager

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

import backend.governance.service as review_service
from backend.db.orm import Base, ReviewDecisionRecord, TaskRecord
from backend.db.repositories import add_task
from backend.governance.service import ReviewConflictError, ReviewTaskNotFoundError
from backend.models import Task


@pytest.fixture
def database(monkeypatch):
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    @contextmanager
    def test_get_db():
        with Session(engine) as db:
            try:
                yield db
                db.commit()
            except Exception:
                db.rollback()
                raise

    monkeypatch.setattr(review_service, "get_db", test_get_db)
    return engine


def _task(task_id, team_id="team-alpha", status="pending_review", deadline=None):
    return Task(
        id=task_id,
        team_id=team_id,
        description=f"Task {task_id}",
        confidence=0.5,
        source_ref="chat.txt:1",
        status=status,
        deadline=deadline,
    )


def _insert(engine, *tasks):
    with Session(engine) as db:
        for task in tasks:
            add_task(db, task)
        db.commit()


def test_review_queue_and_decision_are_team_scoped_and_durable(database):
    _insert(
        database,
        _task("pending-a"),
        _task("pending-b", team_id="team-beta"),
        _task("auto", status="approved"),
    )

    assert [task.id for task in review_service.list_review_tasks("team-alpha")] == [
        "pending-a"
    ]
    with pytest.raises(ReviewTaskNotFoundError):
        review_service.decide_task(
            task_id="pending-b",
            team_id="team-alpha",
            reviewer_id="reviewer-1",
            decision="approved",
        )

    outcome = review_service.decide_task(
        task_id="pending-a",
        team_id="team-alpha",
        reviewer_id="reviewer-1",
        decision="rejected",
        reason="Not actionable",
    )

    assert outcome.task.status == "rejected"
    assert outcome.decision.reason == "Not actionable"
    with Session(database) as db:
        stored = db.get(TaskRecord, "pending-a")
        count = db.execute(select(func.count()).select_from(ReviewDecisionRecord)).scalar_one()
        assert stored.status == "rejected"
        assert count == 1


def test_final_review_decision_cannot_be_repeated_or_contradicted(database):
    _insert(database, _task("task-1"))
    review_service.decide_task(
        task_id="task-1",
        team_id="team-alpha",
        reviewer_id="reviewer-1",
        decision="approved",
    )

    for decision in ("approved", "rejected"):
        with pytest.raises(ReviewConflictError):
            review_service.decide_task(
                task_id="task-1",
                team_id="team-alpha",
                reviewer_id="reviewer-2",
                decision=decision,
            )

    with Session(database) as db:
        count = db.execute(select(func.count()).select_from(ReviewDecisionRecord)).scalar_one()
        assert count == 1


def test_only_approved_valid_tasks_are_execution_candidates(database):
    _insert(
        database,
        _task("approved", status="approved", deadline="2026-09-30T10:00:00Z"),
        _task("approved-no-deadline", status="approved"),
        _task("rejected", status="rejected", deadline="2026-09-30T10:00:00Z"),
        _task("review", deadline="2026-09-30T10:00:00Z"),
        _task(
            "other-team",
            team_id="team-beta",
            status="approved",
            deadline="2026-09-30T10:00:00Z",
        ),
    )

    assert [task.id for task in review_service.execution_candidates("team-alpha")] == [
        "approved"
    ]


def test_service_rejects_unknown_decision(database):
    with pytest.raises(ValueError, match="Unsupported review decision"):
        review_service.decide_task(
            task_id="missing",
            team_id="team-alpha",
            reviewer_id="reviewer-1",
            decision="maybe",
        )

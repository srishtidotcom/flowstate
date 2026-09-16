import os
from contextlib import contextmanager
from dataclasses import dataclass

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import backend.core.activity.engine as activity_engine
from backend.core.graph.dag import GraphCycleError
from backend.db.orm import (
    Base,
    CommitmentRecord,
    EventRecord,
    GraphEdgeRecord,
    TaskRecord,
)
from backend.models import Task


@dataclass
class StubChunk:
    text: str
    speaker: str | None = None


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

    monkeypatch.setattr(activity_engine, "get_db", test_get_db)
    return engine


def _job():
    return {
        "job_id": "job-1",
        "team_id": "team-alpha",
        "filename": "launch_chat.txt",
        "file_type": ".txt",
        "file_path": "/objects/job-1.txt",
    }


def _tasks():
    first = Task(
        id="task-1",
        description="Prepare demo",
        confidence=0.95,
        source_ref="launch_chat.txt:1",
        source_snippet="Siya: Prepare the demo",
        team_id="team-alpha",
        owner="Siya",
        deadline="2026-09-01T10:00:00+00:00",
        status="approved",
    )
    second = Task(
        id="task-2",
        description="Launch product",
        confidence=0.91,
        source_ref="launch_chat.txt:2",
        team_id="team-alpha",
        dependencies=["Prepare demo"],
        status="pending",
    )
    return [first, second]


def _count(db, record_type):
    return db.execute(select(func.count()).select_from(record_type)).scalar_one()


def test_activity_is_persisted_with_provenance_and_dependency_edges(database):
    chunks = [StubChunk("Prepare the demo", "Siya"), StubChunk("Then launch", "Srishti")]

    result = activity_engine.persist_extracted_activity(_job(), chunks, _tasks())

    with Session(database) as db:
        assert _count(db, EventRecord) == 1
        assert _count(db, CommitmentRecord) == 1
        assert _count(db, TaskRecord) == 2
        assert _count(db, GraphEdgeRecord) == 6

        stored_event = db.get(EventRecord, result.event.id)
        stored_tasks = db.execute(select(TaskRecord).order_by(TaskRecord.id)).scalars().all()
        relationships = set(
            db.execute(select(GraphEdgeRecord.relationship_type)).scalars().all()
        )

        assert stored_event.participants == ["Siya", "Srishti"]
        assert stored_event.raw["job_id"] == "job-1"
        assert all(task.commitment_id == result.commitment.id for task in stored_tasks)
        assert stored_tasks[0].source_snippet == "Siya: Prepare the demo"
        assert relationships == {"belongs_to", "depends_on", "inferred_from"}


def test_database_failure_rolls_back_every_activity_record(database, monkeypatch):
    original_add_task = activity_engine.add_task
    calls = 0

    def fail_second_task(db, task):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise IntegrityError("insert", {}, RuntimeError("forced failure"))
        return original_add_task(db, task)

    monkeypatch.setattr(activity_engine, "add_task", fail_second_task)

    with pytest.raises(IntegrityError):
        activity_engine.persist_extracted_activity(_job(), [], _tasks())

    with Session(database) as db:
        assert _count(db, EventRecord) == 0
        assert _count(db, CommitmentRecord) == 0
        assert _count(db, TaskRecord) == 0
        assert _count(db, GraphEdgeRecord) == 0


def test_dependency_cycle_is_rejected_before_persistence(database):
    tasks = _tasks()
    tasks[0].dependencies = [tasks[1].description]

    with pytest.raises(GraphCycleError):
        activity_engine.persist_extracted_activity(_job(), [], tasks)

    with Session(database) as db:
        assert _count(db, EventRecord) == 0
        assert _count(db, CommitmentRecord) == 0
        assert _count(db, TaskRecord) == 0
        assert _count(db, GraphEdgeRecord) == 0


def test_reprocessing_same_task_ids_does_not_create_partial_duplicates(database):
    tasks = _tasks()
    first = activity_engine.persist_extracted_activity(_job(), [], tasks)
    second = activity_engine.persist_extracted_activity(_job(), [], _tasks())

    assert second.event.id == first.event.id
    assert second.commitment.id == first.commitment.id
    assert [task.id for task in second.tasks] == [task.id for task in first.tasks]

    with Session(database) as db:
        assert _count(db, EventRecord) == 1
        assert _count(db, CommitmentRecord) == 1
        assert _count(db, TaskRecord) == 2
        assert _count(db, GraphEdgeRecord) == 6

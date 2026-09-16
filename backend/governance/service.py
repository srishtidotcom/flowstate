"""Auditable governance and review lifecycle."""

from dataclasses import dataclass
from typing import List

from sqlalchemy.exc import IntegrityError

from backend.db.database import get_db
from backend.db.repositories import (
    add_review_decision,
    find_review_decision,
    find_task_record,
    list_execution_candidate_records,
    list_review_task_records,
    review_decision_from_record,
    task_from_record,
    update_task_status,
)
from backend.models import ReviewDecision, Task


ALLOWED_DECISIONS = {"approved", "rejected"}


class ReviewTaskNotFoundError(LookupError):
    pass


class ReviewConflictError(RuntimeError):
    pass


@dataclass(frozen=True)
class ReviewOutcome:
    task: Task
    decision: ReviewDecision


def list_review_tasks(team_id: str) -> List[Task]:
    with get_db() as db:
        return [task_from_record(record) for record in list_review_task_records(db, team_id)]


def decide_task(
    *,
    task_id: str,
    team_id: str,
    reviewer_id: str,
    decision: str,
    reason: str | None = None,
) -> ReviewOutcome:
    if decision not in ALLOWED_DECISIONS:
        raise ValueError(f"Unsupported review decision: {decision}")

    try:
        with get_db() as db:
            task_record = find_task_record(db, task_id, team_id)
            if task_record is None:
                raise ReviewTaskNotFoundError(task_id)
            if task_record.status != "pending_review":
                raise ReviewConflictError(
                    f"Task {task_id} is already in final state {task_record.status}"
                )
            if find_review_decision(db, task_id, team_id) is not None:
                raise ReviewConflictError(f"Task {task_id} already has a final decision")

            domain_decision = ReviewDecision(
                team_id=team_id,
                task_id=task_id,
                reviewer_id=reviewer_id,
                decision=decision,
                reason=reason,
            )
            add_review_decision(db, domain_decision)
            updated = update_task_status(db, task_id, team_id, decision)
            assert updated is not None
            return ReviewOutcome(
                task=task_from_record(updated),
                decision=domain_decision,
            )
    except IntegrityError as exc:
        raise ReviewConflictError(f"Task {task_id} already has a final decision") from exc


def execution_candidates(team_id: str) -> List[Task]:
    with get_db() as db:
        return [
            task_from_record(record)
            for record in list_execution_candidate_records(db, team_id)
        ]

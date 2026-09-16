"""Thin human review API."""

from fastapi import APIRouter, HTTPException, Query

from backend.governance.service import (
    ReviewConflictError,
    ReviewTaskNotFoundError,
    decide_task,
    list_review_tasks,
)
from backend.models.schemas import (
    ReviewDecisionRequest,
    ReviewDecisionResponse,
    TaskResponse,
)


router = APIRouter(prefix="/review", tags=["review"])


@router.get("/tasks", response_model=list[TaskResponse])
async def review_tasks(team_id: str = Query(min_length=1)) -> list[TaskResponse]:
    return [TaskResponse.from_domain(task) for task in list_review_tasks(team_id)]


@router.post(
    "/tasks/{task_id}/decision",
    response_model=ReviewDecisionResponse,
)
async def review_decision(
    task_id: str,
    request: ReviewDecisionRequest,
    team_id: str = Query(min_length=1),
) -> ReviewDecisionResponse:
    try:
        outcome = decide_task(
            task_id=task_id,
            team_id=team_id,
            reviewer_id=request.reviewer_id,
            decision=request.decision,
            reason=request.reason,
        )
    except ReviewTaskNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Review task not found") from exc
    except ReviewConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ReviewDecisionResponse.from_domains(outcome.decision, outcome.task)

"""Thin job lifecycle and results API."""

from fastapi import APIRouter, HTTPException, Query

from backend.ingestion.service import JobNotCompletedError, get_job, get_job_results
from backend.models.schemas import (
    CommitmentResponse,
    EventResponse,
    GraphEdgeResponse,
    JobResponse,
    JobResultsResponse,
    TaskResponse,
)


router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}", response_model=JobResponse)
async def job_status(job_id: str, team_id: str = Query(min_length=1)) -> JobResponse:
    job = get_job(job_id, team_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobResponse.from_domain(job)


@router.get("/{job_id}/results", response_model=JobResultsResponse)
async def job_results(job_id: str, team_id: str = Query(min_length=1)) -> JobResultsResponse:
    try:
        results = get_job_results(job_id, team_id)
    except JobNotCompletedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if results is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobResultsResponse(
        job=JobResponse.from_domain(results.job),
        event=EventResponse.from_domain(results.event),
        commitment=CommitmentResponse.from_domain(results.commitment),
        tasks=[TaskResponse.from_domain(task) for task in results.tasks],
        edges=[GraphEdgeResponse.from_domain(edge) for edge in results.edges],
    )

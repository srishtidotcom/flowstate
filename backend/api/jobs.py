"""Job lifecycle API."""

from fastapi import APIRouter, HTTPException

from backend.ingestion.service import get_job


router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}")
def job_status(job_id: str, team_id: str):
    job = get_job(job_id, team_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    response = job.to_dict()
    response.pop("file_path", None)
    return response

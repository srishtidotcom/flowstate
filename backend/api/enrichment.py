from fastapi import APIRouter, HTTPException
from backend.models import Task
from backend.enrichment.pipeline import enrich_task

router = APIRouter()

@router.post("/enrich")
async def enrich(task: Task):
    try:
        enriched_task = enrich_task(task, task.team_id)
        return {"status": "success", "data": enriched_task.dict()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
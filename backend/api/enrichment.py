from fastapi import APIRouter, HTTPException
from backend.enrichment.pipeline import enrich_task
from backend.models.schemas import TaskEnrichmentRequest, TaskResponse

router = APIRouter()

@router.post("/enrich")
async def enrich(request: TaskEnrichmentRequest) -> TaskResponse:
    try:
        task = request.to_domain()
        enriched_task = enrich_task(task, task.team_id)
        return TaskResponse.from_domain(enriched_task)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

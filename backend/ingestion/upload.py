import uuid
import os
import redis
from fastapi import APIRouter, HTTPException, UploadFile, File, Form

from backend.ingestion.service import enqueue_upload_job
from backend.models import Job

router = APIRouter()

OBJECT_STORE_PATH = os.getenv("OBJECT_STORE_PATH", "./storage/objects")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

r = redis.from_url(REDIS_URL)

ALLOWED_EXTENSIONS = {".txt", ".pdf", ".docx", ".png", ".jpg", ".json"}

@router.post("/upload")
async def upload_file(file: UploadFile = File(...), team_id: str = Form(...)):
    # Validate file type
    filename = file.filename or "upload"
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=415, detail=f"Unsupported file type: {ext}")

    # Save file to object store
    job_id = str(uuid.uuid4())
    save_path = os.path.join(OBJECT_STORE_PATH, f"{job_id}{ext}")
    os.makedirs(OBJECT_STORE_PATH, exist_ok=True)

    with open(save_path, "wb") as f:
        content = await file.read()
        f.write(content)

    # Push job to Redis queue
    job = Job(
        id=job_id,
        type="process_upload",
        team_id=team_id,
        filename=filename,
        file_path=save_path,
        file_type=ext,
    )
    try:
        enqueue_upload_job(job, r)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Could not queue upload") from exc

    return {"job_id": job_id, "status": "queued", "filename": filename}

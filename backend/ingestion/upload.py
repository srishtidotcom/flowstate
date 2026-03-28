import uuid
import os
import redis
import json
from fastapi import APIRouter, UploadFile, File, Form

router = APIRouter()

OBJECT_STORE_PATH = os.getenv("OBJECT_STORE_PATH", "./storage/objects")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

r = redis.from_url(REDIS_URL)

ALLOWED_EXTENSIONS = {".txt", ".pdf", ".docx", ".png", ".jpg", ".json"}

@router.post("/upload")
async def upload_file(file: UploadFile = File(...), team_id: str = Form(...)):
    # Validate file type
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return {"error": f"Unsupported file type: {ext}"}

    # Save file to object store
    job_id = str(uuid.uuid4())
    save_path = os.path.join(OBJECT_STORE_PATH, f"{job_id}{ext}")
    os.makedirs(OBJECT_STORE_PATH, exist_ok=True)

    with open(save_path, "wb") as f:
        content = await file.read()
        f.write(content)

    # Push job to Redis queue
    job = {
        "job_id": job_id,
        "team_id": team_id,
        "filename": file.filename,
        "file_path": save_path,
        "file_type": ext
    }
    r.lpush("flowstate:jobs", json.dumps(job))

    return {"job_id": job_id, "status": "queued", "filename": file.filename}
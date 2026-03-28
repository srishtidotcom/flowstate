import json
import redis
import os
from backend.preprocessing.normalizer import normalize
from backend.extraction.extractor import extract_tasks

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
r = redis.from_url(REDIS_URL)

def process_job(job: dict):
    print(f"Processing job: {job['job_id']}")

    # Phase 2 — Normalize
    chunks = normalize(job["file_path"], job["file_type"])
    print(f"Got {len(chunks)} chunks")

    # Phase 3 — Extract tasks
    tasks = extract_tasks(chunks)
    print(f"Extracted {len(tasks)} tasks:")
    for t in tasks:
        print(f"  - {t.title} | owner: {t.owner} | deadline: {t.deadline} | confidence: {t.confidence}")

    return tasks

def run_worker():
    print("Worker is listening for jobs...")
    while True:
        _, data = r.brpop("flowstate:jobs")
        job = json.loads(data)
        process_job(job)

if __name__ == "__main__":
    run_worker()
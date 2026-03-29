import json
import redis
import os
import uuid
from sentence_transformers import SentenceTransformer
from backend.preprocessing.normalizer import normalize
from backend.extraction.extractor import extract_tasks
from backend.enrichment.pipeline import enrich_task
from backend.graph.dag import get_dag_summary
from backend.vector_db import store_task, query_similar_tasks
from backend.models import Task

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
r = redis.from_url(REDIS_URL)
model = SentenceTransformer("all-MiniLM-L6-v2")

def process_job(job: dict):
    print(f"\nProcessing job: {job['job_id']}")

    # Phase 2 — Normalize
    chunks = normalize(job["file_path"], job["file_type"])
    print(f"Got {len(chunks)} chunks")

    # Phase 3 — Extract tasks
    tasks = extract_tasks(chunks)
    print(f"Extracted {len(tasks)} tasks")

    # Phase 4 — Enrich + Phase 7 — Store in ChromaDB
    enriched_tasks = []
    for task in tasks:
        owner = task.owner
        if isinstance(owner, list):
            owner = ", ".join(owner)

        t = Task(
            task_id=str(uuid.uuid4()),
            task=task.title,
            owner=owner,
            deadline=task.deadline,
            confidence=task.confidence,
            source_ref=job["filename"],
            team_id=job["team_id"]
        )

        # Enrich
        enriched = enrich_task(t, job["team_id"])
        enriched_tasks.append(enriched)

        # Generate embedding and store in ChromaDB
        embedding = model.encode(enriched.task).tolist()
        store_task(enriched, embedding)

        print(f"  - {enriched.task} | owner: {enriched.owner or enriched.inferred_owner} | deadline: {enriched.deadline} | confidence: {enriched.confidence}")

    # Phase 5 — Build DAG
    dag_summary = get_dag_summary(enriched_tasks)
    print(f"\nDAG Summary:")
    print(f"  Total tasks: {dag_summary['total_tasks']}")
    print(f"  Dependencies: {dag_summary['total_dependencies']}")
    print(f"  Critical path: {dag_summary['critical_path']}")
    print(f"  Bottlenecks: {dag_summary['bottlenecks']}")

    return enriched_tasks

def run_worker():
    print("Worker is listening for jobs...")
    while True:
        _, data = r.brpop("flowstate:jobs")
        job = json.loads(data)
        process_job(job)

if __name__ == "__main__":
    run_worker()
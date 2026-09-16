"""Redis worker orchestration for the durable upload pipeline."""

import json
import os
from typing import Any, Callable, Iterable

import redis

from backend.core.activity.engine import ActivityPersistenceResult, persist_extracted_activity
from backend.enrichment.pipeline import enrich_task
from backend.extraction.extractor import extract_tasks
from backend.governance.router import classify_tasks
from backend.ingestion.service import claim_job, mark_job_completed, set_job_status
from backend.models import Task
from backend.preprocessing.normalizer import normalize


REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
QUEUE_NAME = "flowstate:jobs"
r = redis.from_url(REDIS_URL)


def process_job(
    job: dict,
    *,
    normalizer: Callable[[str, str], Iterable[Any]] = normalize,
    extractor: Callable[[list[Any]], Iterable[Any]] = extract_tasks,
    enricher: Callable[[Task, str], Task] = enrich_task,
    embedder: Callable[[list[str]], list[list[float]]] | None = None,
    vector_store: Callable[[list[Task], list[list[float]]], None] | None = None,
) -> ActivityPersistenceResult:
    """Run one claimed upload through deterministic boundaries."""
    chunks = list(normalizer(job["file_path"], job["file_type"]))
    _bind_original_filename(chunks, job["filename"])
    extracted = list(extractor(chunks))

    tasks = []
    for item in extracted:
        owner = item.owner
        if isinstance(owner, list):
            owner = ", ".join(owner)
        task = Task(
            description=item.title,
            owner=owner,
            deadline=item.deadline,
            confidence=item.confidence,
            source_ref=getattr(item, "source_ref", None) or job["filename"],
            source_snippet=getattr(item, "source_snippet", None),
            team_id=job["team_id"],
            dependencies=list(item.dependencies or []),
        )
        tasks.append(enricher(task, job["team_id"]))

    routing = classify_tasks(tasks)
    for task in routing["approved"]:
        task.status = "approved"
    for task in routing["review"]:
        task.status = "pending_review"

    persisted = persist_extracted_activity(job, chunks, tasks)

    if persisted.tasks:
        encode = embedder or _default_embedder
        store = vector_store or _default_vector_store
        embeddings = encode([task.description for task in persisted.tasks])
        store(persisted.tasks, embeddings)

    return persisted


def process_queued_job(
    job: dict,
    *,
    processor: Callable[[dict], ActivityPersistenceResult] = process_job,
) -> ActivityPersistenceResult:
    """Claim once, record failures, and complete one durable job."""
    job_id = job.get("job_id")
    team_id = job.get("team_id")
    if not job_id or not team_id:
        raise ValueError("Queued job must include job_id and team_id")

    if not claim_job(job_id, team_id):
        raise ValueError(f"Job {job_id} is missing or has already been claimed")
    try:
        if job.get("type") != "process_upload":
            raise ValueError(f"Unsupported job type: {job.get('type')!r}")
        result = processor(job)
    except Exception as exc:
        set_job_status(job_id, team_id, "failed", str(exc))
        raise

    if not mark_job_completed(
        job_id,
        team_id,
        result.event.id,
        result.commitment.id,
    ):
        raise RuntimeError(f"Could not complete job {job_id}")
    return result


def run_worker(queue: Any = r) -> None:
    print("Worker is listening for jobs...")
    while True:
        _, data = queue.brpop(QUEUE_NAME)
        try:
            job = json.loads(data)
            process_queued_job(job)
        except Exception as exc:
            print(f"[worker] Job failed: {exc}")


def _default_embedder(texts: list[str]) -> list[list[float]]:
    from backend.ml import model

    return model.encode(texts, show_progress_bar=False).tolist()


def _default_vector_store(tasks: list[Task], embeddings: list[list[float]]) -> None:
    from backend.vector_db import store_tasks_batch

    store_tasks_batch(tasks, embeddings)


def _bind_original_filename(chunks: list[Any], filename: str) -> None:
    """Replace object-store names while preserving exact source locators."""
    for chunk in chunks:
        source_ref = getattr(chunk, "source_ref", "")
        if not source_ref:
            continue
        _, separator, locator = source_ref.partition(":")
        chunk.source_ref = f"{filename}:{locator}" if separator else filename


if __name__ == "__main__":
    run_worker()

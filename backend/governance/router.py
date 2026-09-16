import redis
import json
import logging
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict
from backend.governance.policy import requires_review
from backend.models.domain import Task


# --- Config ---
class Settings(BaseSettings):
    REDIS_URL: str = "redis://localhost:6379"
    EXTRACTION_CONFIDENCE_THRESHOLD: float = 0.75
    OWNERSHIP_INFERENCE_THRESHOLD: float = 0.70

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
r = redis.from_url(settings.REDIS_URL)
logging.basicConfig(level=logging.INFO)

# --- Routing Logic ---
def classify_task(task: Task) -> str:
    needs_review = requires_review(
        task,
        extraction_threshold=settings.EXTRACTION_CONFIDENCE_THRESHOLD,
        ownership_threshold=settings.OWNERSHIP_INFERENCE_THRESHOLD,
    )
    return "review" if needs_review else "approved"


def classify_tasks(tasks: List[Task]) -> dict:
    results = {"approved": [], "review": []}
    for task in tasks:
        results[classify_task(task)].append(task)
    return results


def enqueue_routing(routing: dict) -> None:
    for status, tasks in routing.items():
        queue = f"flowstate:{status}"
        for task in tasks:
            r.lpush(queue, json.dumps(task.to_dict()))
            logging.info(f"Task routed to {queue}: {task.description}")


def route_task(task: Task) -> str:
    """Classify and enqueue one task."""
    try:
        status = classify_task(task)
        queue = f"flowstate:{status}"
        r.lpush(queue, json.dumps(task.to_dict()))
        logging.info(f"Task routed to {queue}: {task.description}")
        return status
    except Exception as e:
        logging.error(f"Error routing task: {e}")
        raise

def route_tasks(tasks: List[Task]) -> dict:
    """Classify a list, then publish its routing side effects."""
    routing = classify_tasks(tasks)
    enqueue_routing(routing)
    return routing

import os
from typing import Optional, List
from backend.models import Task


DUPLICATE_THRESHOLD = float(os.getenv("DUPLICATE_SIMILARITY_THRESHOLD", "0.85"))


def detect_duplicates(
    task: Task,
    team_id: str,
    similarity_threshold: float = DUPLICATE_THRESHOLD,
) -> Optional[List[Task]]:
    """
    Detect duplicate tasks by comparing embeddings in ChromaDB.
    Returns list of potential duplicates if similarity > threshold.
    """
    if not task.description:
        return None

    # Keep model/vector initialization lazy so deterministic tests and API
    # imports never contact external services.
    from backend.ml import model
    from backend.vector_db import query_similar_tasks

    # Generate embedding for the new task
    embedding = model.encode(task.description).tolist()

    # Query ChromaDB for similar tasks
    results = query_similar_tasks(team_id, embedding, top_k=3)

    # Filter for tasks with overlapping owner/deadline
    duplicates = []
    if results and results.get("documents"):
        for i, doc in enumerate(results["documents"][0]):
            metadata = results["metadatas"][0][i]
            if (
                (task.owner and task.owner == metadata.get("owner")) or
                (task.deadline and task.deadline == metadata.get("deadline"))
            ):
                duplicates.append(doc)

    return duplicates if duplicates else None

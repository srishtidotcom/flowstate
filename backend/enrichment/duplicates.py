from typing import Optional, List
from backend.models import Task
from backend.vector_db import ChromaDBClient
from sentence_transformers import SentenceTransformer

model = SentenceTransformer("all-MiniLM-L6-v2")
chroma = ChromaDBClient()

def detect_duplicates(task: Task, team_id: str, similarity_threshold: float = 0.92) -> Optional[List[Task]]:
    """
    Detect duplicate tasks by comparing embeddings in ChromaDB.
    Returns list of potential duplicates if similarity > threshold.
    """
    if not task.task:
        return None

    # Generate embedding for the new task
    embedding = model.encode(task.task).tolist()

    # Query ChromaDB for similar tasks
    similar_tasks = chroma.query(
        collection=f"tasks_{team_id}",
        query_embedding=embedding,
        top_k=3,
        threshold=similarity_threshold
    )

    # Filter for tasks with overlapping owner/deadline
    duplicates = []
    for similar_task in similar_tasks:
        if (
            (task.owner and task.owner == similar_task.owner) or
            (task.deadline and task.deadline == similar_task.deadline)
        ):
            duplicates.append(similar_task)

    return duplicates if duplicates else None
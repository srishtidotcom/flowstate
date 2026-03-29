import chromadb
import os
from typing import List, Optional
from backend.models import Task

CHROMA_HOST = os.getenv("CHROMA_HOST", "localhost")
CHROMA_PORT = int(os.getenv("CHROMA_PORT", "8000"))

client = chromadb.HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)

def get_or_create_collection(team_id: str):
    return client.get_or_create_collection(name=f"tasks_{team_id}")

def store_task(task: Task, embedding: List[float]):
    """Store a task and its embedding in ChromaDB."""
    collection = get_or_create_collection(task.team_id)
    collection.upsert(
        ids=[task.task_id or task.task],
        embeddings=[embedding],
        documents=[task.task],
        metadatas=[{
            "owner": task.owner or "",
            "deadline": task.deadline or "",
            "confidence": str(task.confidence),
            "source_ref": task.source_ref,
            "team_id": task.team_id
        }]
    )

def query_similar_tasks(team_id: str, embedding: List[float], top_k: int = 3) -> List[dict]:
    """Query ChromaDB for similar tasks."""
    collection = get_or_create_collection(team_id)
    results = collection.query(
        query_embeddings=[embedding],
        n_results=top_k
    )
    return results
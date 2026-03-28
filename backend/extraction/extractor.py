import httpx
import json
import os
from typing import List, Optional
from dataclasses import dataclass
from backend.preprocessing.normalizer import Chunk

OLLAMA_API_BASE = os.getenv("OLLAMA_API_BASE", "http://localhost:11434")

@dataclass
class ExtractedTask:
    title: str
    owner: Optional[str] = None
    deadline: Optional[str] = None
    confidence: float = 0.0
    source_snippet: Optional[str] = None

SYSTEM_PROMPT = """
You are a task extraction assistant. Given a conversation, extract all actionable tasks.
For each task return a JSON array where each item has:
- title: short description of the task
- owner: person responsible (null if unclear)
- deadline: deadline mentioned (null if none)
- confidence: float 0-1 of how confident you are this is a real task

Return ONLY a valid JSON array, no explanation, no markdown.
"""

def extract_tasks(chunks: List[Chunk]) -> List[ExtractedTask]:
    conversation = "\n".join(
        [f"{c.speaker}: {c.text}" if c.speaker else c.text for c in chunks]
    )

    response = httpx.post(
        f"{OLLAMA_API_BASE}/api/chat",
        json={
            "model": "mistral",
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": conversation}
            ],
            "stream": False
        },
        timeout=120.0
    )

    raw = response.json()["message"]["content"]

    try:
        tasks_data = json.loads(raw)
    except json.JSONDecodeError:
        # Try to extract JSON array from response if model added extra text
        start = raw.find("[")
        end = raw.rfind("]") + 1
        tasks_data = json.loads(raw[start:end])

    tasks = []
    for t in tasks_data:
        tasks.append(ExtractedTask(
            title=t.get("title", ""),
            owner=t.get("owner"),
            deadline=t.get("deadline"),
            confidence=t.get("confidence", 0.5),
            source_snippet=None
        ))
    return tasks
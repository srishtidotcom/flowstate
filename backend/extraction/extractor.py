"""Schema-enforced Ollama boundary for task extraction."""

import json
import os
from dataclasses import dataclass, field
from typing import Callable, List, Optional

import httpx
import jsonschema

from backend.preprocessing.normalizer import Chunk


OLLAMA_API_BASE = os.getenv("OLLAMA_API_BASE", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "mistral")
BATCH_SIZE = 100
MAX_CHUNKS = 1000


class ExtractionError(RuntimeError):
    """The extraction boundary could not produce validated task data."""


@dataclass(frozen=True)
class ExtractedTask:
    """Validated extraction transport converted to a canonical Task by the worker."""

    title: str
    owner: Optional[str]
    deadline: Optional[str]
    confidence: float
    source_ref: str
    source_snippet: str
    dependencies: List[str] = field(default_factory=list)


TASK_LIST_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "title": {"type": "string", "minLength": 1},
            "owner": {"type": ["string", "null"]},
            "deadline": {"type": ["string", "null"]},
            "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
            "dependencies": {
                "type": "array",
                "items": {"type": "string", "minLength": 1},
            },
            "source_id": {
                "type": "string",
                "minLength": 1,
                "pattern": "^source_[1-9][0-9]*$",
            },
        },
        "required": [
            "title",
            "owner",
            "deadline",
            "confidence",
            "dependencies",
            "source_id",
        ],
    },
}


SYSTEM_PROMPT = f"""
You extract actionable tasks from normalized source chunks.
Return JSON only: one array and no preamble, markdown, comments, or trailing text.
Every item must validate against this exact JSON Schema:
{json.dumps(TASK_LIST_SCHEMA, sort_keys=True)}

Copy source_id exactly from the bracketed local ID for the source chunk that
supports the task. Never invent an ID. Use null when an owner or deadline is not
present. Keep dependency titles identical to another extracted title.

Examples:

Input: [source_1] Asha: Rahul, send the revised deck tomorrow.
Output: [{{"title":"Send the revised deck","owner":"Rahul","deadline":"tomorrow","confidence":0.96,"dependencies":[],"source_id":"source_1"}}]

Input: [source_1] We should verify the launch metrics.
Output: [{{"title":"Verify the launch metrics","owner":null,"deadline":null,"confidence":0.82,"dependencies":[],"source_id":"source_1"}}]

Input: [source_1] Priya will submit the budget by EOD Friday.
Output: [{{"title":"Submit the budget","owner":"Priya","deadline":"by EOD Friday","confidence":0.97,"dependencies":[],"source_id":"source_1"}}]

Input: [source_1] Sam: Draft the proposal today. [source_2] Lee: Review the proposal after Sam drafts it.
Output: [{{"title":"Draft the proposal","owner":"Sam","deadline":"today","confidence":0.94,"dependencies":[],"source_id":"source_1"}},{{"title":"Review the proposal","owner":"Lee","deadline":null,"confidence":0.91,"dependencies":["Draft the proposal"],"source_id":"source_2"}}]
""".strip()


def extract_tasks(
    chunks: List[Chunk],
    *,
    post: Callable[..., httpx.Response] = httpx.post,
) -> List[ExtractedTask]:
    """Extract every batch or fail the entire extraction operation."""
    all_tasks: List[ExtractedTask] = []
    limited_chunks = chunks[:MAX_CHUNKS]

    for offset in range(0, len(limited_chunks), BATCH_SIZE):
        batch = limited_chunks[offset : offset + BATCH_SIZE]
        source_map = _source_map(batch, offset)
        conversation = "\n".join(
            f"[{source_id}] "
            f"{chunk.speaker + ': ' if chunk.speaker else ''}{chunk.text}"
            for source_id, (_, chunk) in source_map.items()
        )
        raw_output = _call_ollama(conversation, post=post)
        all_tasks.extend(validate_extraction(raw_output, source_map))

    return all_tasks


def validate_extraction(
    raw_output: str,
    source_map: dict[str, tuple[str, Chunk]],
) -> List[ExtractedTask]:
    """Validate raw model JSON and bind references to exact source text."""
    try:
        data = json.loads(raw_output)
    except (json.JSONDecodeError, TypeError) as exc:
        raise ExtractionError("Ollama returned malformed JSON") from exc

    try:
        jsonschema.validate(data, TASK_LIST_SCHEMA)
    except jsonschema.ValidationError as exc:
        raise ExtractionError(f"Ollama response violated the task schema: {exc.message}") from exc

    tasks = []
    for item in data:
        source_id = item["source_id"]
        if source_id not in source_map:
            raise ExtractionError(f"Ollama returned unknown source_id: {source_id}")
        source_ref, chunk = source_map[source_id]
        tasks.append(
            ExtractedTask(
                title=item["title"],
                owner=item["owner"],
                deadline=item["deadline"],
                confidence=item["confidence"],
                dependencies=item["dependencies"],
                source_ref=source_ref,
                source_snippet=chunk.text,
            )
        )
    return tasks


def _call_ollama(
    conversation: str,
    *,
    post: Callable[..., httpx.Response],
) -> str:
    try:
        response = post(
            f"{OLLAMA_API_BASE}/api/chat",
            json={
                "model": OLLAMA_MODEL,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": conversation},
                ],
                "stream": False,
                "format": TASK_LIST_SCHEMA,
            },
            timeout=120.0,
        )
        response.raise_for_status()
    except httpx.TimeoutException as exc:
        raise ExtractionError("Ollama extraction request timed out") from exc
    except httpx.RequestError as exc:
        raise ExtractionError(f"Could not connect to Ollama: {exc}") from exc
    except httpx.HTTPStatusError as exc:
        raise ExtractionError(f"Ollama returned HTTP {exc.response.status_code}") from exc

    try:
        content = response.json()["message"]["content"]
    except (ValueError, KeyError, TypeError) as exc:
        raise ExtractionError("Ollama response envelope was invalid") from exc
    if not isinstance(content, str):
        raise ExtractionError("Ollama response content was not text")
    return content


def _source_map(
    chunks: List[Chunk],
    offset: int,
) -> dict[str, tuple[str, Chunk]]:
    result = {}
    for local_index, chunk in enumerate(chunks, start=1):
        source_id = f"source_{local_index}"
        source_ref = chunk.source_ref or f"chunk:{offset + local_index}"
        result[source_id] = (source_ref, chunk)
    return result

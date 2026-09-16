"""Activity Engine: persist extracted knowledge as one relational transaction."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, List
from uuid import NAMESPACE_URL, uuid5

from backend.core.graph.dag import validate_dependency_edges
from backend.db.database import get_db
from backend.db.repositories import (
    add_commitment,
    add_event,
    add_graph_edges,
    add_task,
    commitment_from_record,
    event_from_record,
    find_commitment,
    find_event,
    graph_edge_from_record,
    list_graph_edges,
    list_tasks_for_commitment,
    task_from_record,
)
from backend.models import Commitment, Event, GraphEdge, Task


@dataclass
class ActivityPersistenceResult:
    event: Event
    commitment: Commitment
    tasks: List[Task]
    edges: List[GraphEdge]


def persist_extracted_activity(
    job: dict,
    chunks: Iterable[Any],
    tasks: List[Task],
    *,
    source_event: Event | None = None,
) -> ActivityPersistenceResult:
    """Persist derived activity atomically, reusing a connector source Event."""
    chunks = list(chunks)
    event = source_event or _source_event(job, chunks)
    if event.team_id != job["team_id"]:
        raise ValueError("Event team_id does not match the job team_id")
    commitment = _source_commitment(job, event, connector_event=source_event is not None)

    for index, task in enumerate(tasks):
        if task.team_id != job["team_id"]:
            raise ValueError("Task team_id does not match the job team_id")
        task.id = _stable_id(job, f"task:{index}:{task.description}")
        task.commitment_id = commitment.id

    edges = _graph_edges(job, event, commitment, tasks)
    validate_dependency_edges(edges)

    with get_db() as db:
        existing_event = find_event(db, event.id, job["team_id"])
        existing_commitment = find_commitment(db, commitment.id, job["team_id"])
        if source_event is not None:
            if existing_event is None:
                raise RuntimeError("Connector source Event is missing")
            if existing_commitment:
                stored_tasks = list_tasks_for_commitment(db, commitment.id, job["team_id"])
                node_ids = [event.id, commitment.id, *(record.id for record in stored_tasks)]
                stored_edges = list_graph_edges(db, job["team_id"], node_ids)
                return ActivityPersistenceResult(
                    event=event_from_record(existing_event),
                    commitment=commitment_from_record(existing_commitment),
                    tasks=[task_from_record(record) for record in stored_tasks],
                    edges=[graph_edge_from_record(record) for record in stored_edges],
                )
        elif existing_event or existing_commitment:
            if not (existing_event and existing_commitment):
                raise RuntimeError("Incomplete persisted activity detected for job")
            stored_tasks = list_tasks_for_commitment(db, commitment.id, job["team_id"])
            node_ids = [event.id, commitment.id, *(record.id for record in stored_tasks)]
            stored_edges = list_graph_edges(db, job["team_id"], node_ids)
            return ActivityPersistenceResult(
                event=event_from_record(existing_event),
                commitment=commitment_from_record(existing_commitment),
                tasks=[task_from_record(record) for record in stored_tasks],
                edges=[graph_edge_from_record(record) for record in stored_edges],
            )
        if source_event is None:
            add_event(db, event)
        add_commitment(db, commitment)
        for task in tasks:
            add_task(db, task)
        add_graph_edges(db, edges)

    return ActivityPersistenceResult(
        event=event,
        commitment=commitment,
        tasks=tasks,
        edges=edges,
    )


def _source_event(job: dict, chunks: List[Any]) -> Event:
    participants = list(
        dict.fromkeys(
            chunk.speaker
            for chunk in chunks
            if getattr(chunk, "speaker", None)
        )
    )
    content = "\n".join(
        f"{chunk.speaker}: {chunk.text}" if getattr(chunk, "speaker", None) else chunk.text
        for chunk in chunks
        if getattr(chunk, "text", "").strip()
    )
    return Event(
        id=_stable_id(job, "event"),
        type="file_upload",
        source="upload",
        content=content,
        participants=participants,
        team_id=job["team_id"],
        raw={
            "job_id": job["job_id"],
            "filename": job.get("filename"),
            "file_type": job.get("file_type"),
            "object_ref": job.get("file_path"),
            "chunk_count": len(chunks),
        },
    )


def _source_commitment(
    job: dict,
    event: Event,
    *,
    connector_event: bool,
) -> Commitment:
    if connector_event:
        return Commitment(
            id=_stable_id(job, "commitment"),
            title=f"Work extracted from {event.source}",
            description=f"Tasks and context extracted from Event {event.id}",
            team_id=job["team_id"],
        )
    filename = job.get("filename") or "uploaded source"
    source_name = Path(filename).stem.replace("_", " ").strip() or filename
    return Commitment(
        id=_stable_id(job, "commitment"),
        title=f"Work extracted from {source_name}",
        description=f"Tasks and context extracted from {filename}",
        team_id=job["team_id"],
    )


def _graph_edges(
    job: dict,
    event: Event,
    commitment: Commitment,
    tasks: List[Task],
) -> List[GraphEdge]:
    edges = [
        GraphEdge(
            source_id=commitment.id,
            target_id=event.id,
            relationship_type="inferred_from",
            team_id=event.team_id,
        )
    ]
    tasks_by_title = {task.description.casefold(): task for task in tasks}

    for task in tasks:
        edges.extend(
            [
                GraphEdge(
                    source_id=task.id,
                    target_id=commitment.id,
                    relationship_type="belongs_to",
                    team_id=task.team_id,
                ),
                GraphEdge(
                    source_id=task.id,
                    target_id=event.id,
                    relationship_type="inferred_from",
                    team_id=task.team_id,
                ),
            ]
        )
        for dependency_title in task.dependencies:
            dependency = tasks_by_title.get(dependency_title.casefold())
            if dependency:
                edges.append(
                    GraphEdge(
                        source_id=dependency.id,
                        target_id=task.id,
                        relationship_type="depends_on",
                        team_id=task.team_id,
                    )
                )
    unique_edges = {
        (edge.source_id, edge.target_id, edge.relationship_type): edge
        for edge in edges
    }
    edges = list(unique_edges.values())
    for edge in edges:
        edge.id = _stable_id(
            job,
            f"edge:{edge.source_id}:{edge.target_id}:{edge.relationship_type}",
        )
    return edges


def _stable_id(job: dict, component: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"flowstate:{job['team_id']}:{job['job_id']}:{component}"))

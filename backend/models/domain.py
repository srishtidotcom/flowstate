"""Infrastructure-independent domain objects for Flowstate."""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _serialize(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, list):
        return [_serialize(item) for item in value]
    if isinstance(value, dict):
        return {key: _serialize(item) for key, item in value.items()}
    return value


class SerializableDomain:
    def to_dict(self) -> Dict[str, Any]:
        return _serialize(asdict(self))

    # Compatibility for the existing API and Redis routing code. New code
    # should prefer the explicit to_dict() name.
    def dict(self) -> Dict[str, Any]:
        return self.to_dict()


@dataclass
class Event(SerializableDomain):
    type: str
    source: str
    content: str
    team_id: str
    id: str = field(default_factory=lambda: str(uuid4()))
    participants: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=utc_now)
    raw: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    deleted_at: Optional[datetime] = None


@dataclass
class Task(SerializableDomain):
    description: str
    confidence: float
    source_ref: str
    team_id: str
    id: str = field(default_factory=lambda: str(uuid4()))
    owner: Optional[str] = None
    inferred_owner: Optional[str] = None
    inference_confidence: Optional[float] = None
    deadline: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)
    duplicate_candidates: List[str] = field(default_factory=list)
    source_snippet: Optional[str] = None
    inference_trace: Optional[str] = None
    commitment_id: Optional[str] = None
    status: str = "pending"
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    deleted_at: Optional[datetime] = None

    @property
    def task(self) -> str:
        """Compatibility alias for the prototype's former field name."""
        return self.description

    @property
    def task_id(self) -> str:
        """Compatibility alias for the prototype's former field name."""
        return self.id


@dataclass
class Commitment(SerializableDomain):
    title: str
    team_id: str
    id: str = field(default_factory=lambda: str(uuid4()))
    description: str = ""
    owner: Optional[str] = None
    deadline: Optional[datetime] = None
    task_ids: List[str] = field(default_factory=list)
    event_ids: List[str] = field(default_factory=list)
    document_ids: List[str] = field(default_factory=list)
    status: str = "active"
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    deleted_at: Optional[datetime] = None


@dataclass
class Entity(SerializableDomain):
    type: str
    name: str
    team_id: str
    id: str = field(default_factory=lambda: str(uuid4()))
    aliases: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    deleted_at: Optional[datetime] = None


@dataclass
class GraphEdge(SerializableDomain):
    source_id: str
    target_id: str
    relationship_type: str
    team_id: str
    id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=utc_now)
    deleted_at: Optional[datetime] = None


@dataclass
class Job(SerializableDomain):
    type: str
    team_id: str
    status: str = "queued"
    id: str = field(default_factory=lambda: str(uuid4()))
    filename: Optional[str] = None
    file_path: Optional[str] = None
    file_type: Optional[str] = None
    error: Optional[str] = None
    attempt_count: int = 0
    queue_published_at: Optional[datetime] = None
    result_event_id: Optional[str] = None
    result_commitment_id: Optional[str] = None
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


@dataclass
class ReviewDecision(SerializableDomain):
    task_id: str
    decision: str
    reviewer_id: str
    team_id: str
    id: str = field(default_factory=lambda: str(uuid4()))
    reason: Optional[str] = None
    created_at: datetime = field(default_factory=utc_now)

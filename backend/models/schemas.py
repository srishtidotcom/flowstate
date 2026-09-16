"""HTTP request/response schemas with explicit domain conversion."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from backend.models.domain import Commitment, Event, GraphEdge, Job, ReviewDecision, Task


class JobResponse(BaseModel):
    id: str
    team_id: str
    type: str
    status: str
    filename: str | None
    error: str | None
    attempt_count: int
    queue_published_at: datetime | None
    result_event_id: str | None
    result_commitment_id: str | None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    completed_at: datetime | None

    @classmethod
    def from_domain(cls, job: Job) -> "JobResponse":
        data = job.to_dict()
        data.pop("file_path", None)
        data.pop("file_type", None)
        return cls.model_validate(data)


class EventResponse(BaseModel):
    id: str
    team_id: str
    type: str
    source: str
    content: str
    participants: list[str]
    timestamp: datetime
    raw: dict[str, Any]

    @classmethod
    def from_domain(cls, event: Event) -> "EventResponse":
        return cls.model_validate(event.to_dict())


class CommitmentResponse(BaseModel):
    id: str
    team_id: str
    title: str
    description: str
    owner: str | None
    deadline: datetime | None
    status: str

    @classmethod
    def from_domain(cls, commitment: Commitment) -> "CommitmentResponse":
        return cls.model_validate(commitment.to_dict())


class TaskResponse(BaseModel):
    id: str
    team_id: str
    commitment_id: str | None
    description: str
    owner: str | None
    inferred_owner: str | None
    inference_confidence: float | None
    deadline: datetime | None
    confidence: float = Field(ge=0.0, le=1.0)
    source_ref: str
    source_snippet: str | None
    inference_trace: str | None
    dependencies: list[str]
    duplicate_candidates: list[str]
    status: str

    @classmethod
    def from_domain(cls, task: Task) -> "TaskResponse":
        return cls.model_validate(task.to_dict())


class GraphEdgeResponse(BaseModel):
    id: str
    team_id: str
    source_id: str
    target_id: str
    relationship_type: str

    @classmethod
    def from_domain(cls, edge: GraphEdge) -> "GraphEdgeResponse":
        return cls.model_validate(edge.to_dict())


class JobResultsResponse(BaseModel):
    job: JobResponse
    event: EventResponse
    commitment: CommitmentResponse
    tasks: list[TaskResponse]
    edges: list[GraphEdgeResponse]


class ReviewDecisionRequest(BaseModel):
    reviewer_id: str = Field(min_length=1, max_length=128)
    decision: Literal["approved", "rejected"]
    reason: str | None = Field(default=None, max_length=4000)


class ReviewDecisionResponse(BaseModel):
    id: str
    team_id: str
    task_id: str
    reviewer_id: str
    decision: Literal["approved", "rejected"]
    reason: str | None
    created_at: datetime
    task: TaskResponse

    @classmethod
    def from_domains(
        cls,
        decision: ReviewDecision,
        task: Task,
    ) -> "ReviewDecisionResponse":
        return cls.model_validate(
            {**decision.to_dict(), "task": TaskResponse.from_domain(task)}
        )


class TaskEnrichmentRequest(BaseModel):
    description: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    source_ref: str = Field(min_length=1)
    team_id: str = Field(min_length=1, max_length=128)
    owner: str | None = None
    deadline: str | None = None
    dependencies: list[str] = Field(default_factory=list)

    def to_domain(self) -> Task:
        return Task(**self.model_dump())

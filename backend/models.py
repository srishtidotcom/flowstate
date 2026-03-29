from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from datetime import datetime

class Chunk(BaseModel):
    """Represents a chunk of normalized text with speaker metadata."""
    text: str
    speaker: Optional[str] = None
    source_ref: str  # Reference to the original file/chunk
    timestamp: Optional[datetime] = None

class Task(BaseModel):
    """Represents a task extracted from a chunk."""
    task_id: Optional[str] = None
    task: str
    owner: Optional[str] = None
    inferred_owner: Optional[str] = None
    inference_confidence: Optional[float] = None
    deadline: Optional[str] = None  # ISO format or relative
    dependencies: List[str] = []
    confidence: float
    source_ref: str
    team_id: str
    duplicate_candidates: List[str] = []

    def dict(self) -> Dict[str, Any]:
        """Return a dictionary representation of the task."""
        return {
            "task_id": self.task_id,
            "task": self.task,
            "owner": self.owner,
            "inferred_owner": self.inferred_owner,
            "inference_confidence": self.inference_confidence,
            "deadline": self.deadline,
            "dependencies": self.dependencies,
            "confidence": self.confidence,
            "source_ref": self.source_ref,
            "team_id": self.team_id,
            "duplicate_candidates": self.duplicate_candidates,
        }
"""Base connector classes and data structures."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class GraphEvent:
	"""Represents a graph state change that may trigger connector actions."""
	event_type: str       # "task_blocked", "deadline_approaching", "blocker_resolved", etc.
	task_id: str
	team_id: str
	metadata: Dict[str, Any]


@dataclass
class ConnectorResult:
	"""Result of executing a connector action."""
	success: bool
	external_id: Optional[str]   # created issue ID, message ID, etc.
	message: str


class BaseConnector(ABC):
	"""Abstract base class for all connectors."""
	
	name: str
	description: str

	def __init__(self, team_id: str, credentials: Optional[Dict[str, Any]] = None):
		self.team_id = team_id
		self.credentials = credentials or {}

	@abstractmethod
	def can_handle(self, event: GraphEvent) -> bool:
		"""Return True if this connector should handle this event."""
		pass

	@abstractmethod
	def execute(self, task: Any, event: GraphEvent) -> ConnectorResult:
		"""Execute the connector action. Must be idempotent."""
		pass

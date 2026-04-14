"""Google Calendar connector — wraps existing calendar automation."""

import hashlib
import os
import redis
from typing import Any, Optional
from flowstate.connectors.base import BaseConnector, ConnectorResult, GraphEvent

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")


def _get_idempotency_key(task_id: str, event_type: str) -> str:
	"""Generate idempotency key to prevent duplicate actions."""
	content = f"google_calendar:{task_id}:{event_type}"
	return hashlib.sha256(content.encode()).hexdigest()


def _already_triggered(key: str) -> bool:
	"""Check if this action has already been triggered."""
	try:
		r = redis.from_url(REDIS_URL)
		return r.sismember("flowstate:connector:triggered", key)
	except Exception:
		return False


def _mark_triggered(key: str):
	"""Mark this action as triggered."""
	try:
		r = redis.from_url(REDIS_URL)
		r.sadd("flowstate:connector:triggered", key)
		r.expire(key, 30 * 24 * 60 * 60)  # Keep for 30 days
	except Exception:
		pass


class GoogleCalendarConnector(BaseConnector):
	"""Schedules tasks as Google Calendar events."""
	
	name = "google_calendar"
	description = "Schedules tasks as Google Calendar events"

	def __init__(self, team_id: str, credentials: Optional[dict] = None):
		super().__init__(team_id=team_id, credentials=credentials)

	def can_handle(self, event: GraphEvent) -> bool:
		"""Handle deadline_approaching events."""
		return event.event_type == "deadline_approaching"

	def execute(self, task: Any, event: GraphEvent) -> ConnectorResult:
		"""Schedule task as calendar event if not already scheduled."""
		# Idempotency check
		idempotency_key = _get_idempotency_key(task.id, event.event_type)
		if _already_triggered(idempotency_key):
			return ConnectorResult(
				success=True,
				external_id=None,
				message=f"Already scheduled: {task.title}"
			)

		try:
			from automation.calendar import schedule_task
			
			event_id = schedule_task(
				title=task.title,
				deadline=task.deadline,
				credentials=self.credentials
			)
			
			_mark_triggered(idempotency_key)
			
			return ConnectorResult(
				success=True,
				external_id=event_id,
				message=f"Scheduled: {task.title}"
			)
		except Exception as e:
			return ConnectorResult(
				success=False,
				external_id=None,
				message=str(e)
			)

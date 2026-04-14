"""Generic webhook connector — POSTs to custom webhooks for any event."""

import hashlib
import json
import os
import redis
from typing import Any, Optional
from flowstate.connectors.base import BaseConnector, ConnectorResult, GraphEvent
from datetime import datetime

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")


def _get_idempotency_key(task_id: str, event_type: str, webhook_url: str) -> str:
	"""Generate idempotency key to prevent duplicate webhook calls."""
	content = f"webhook:{task_id}:{event_type}:{webhook_url}:{datetime.utcnow().date()}"
	return hashlib.sha256(content.encode()).hexdigest()


def _already_fired(key: str) -> bool:
	"""Check if this webhook has already been fired."""
	try:
		r = redis.from_url(REDIS_URL)
		return r.sismember("flowstate:webhook:fired", key)
	except Exception:
		return False


def _mark_fired(key: str):
	"""Mark this webhook as fired."""
	try:
		r = redis.from_url(REDIS_URL)
		r.sadd("flowstate:webhook:fired", key)
		r.expire(key, 30 * 24 * 60 * 60)  # Keep for 30 days
	except Exception:
		pass


class WebhookConnector(BaseConnector):
	"""Generic webhook connector — POSTs to a custom endpoint for any event."""
	
	name = "webhook"
	description = "Generic escape hatch — POSTs to custom webhooks for any event"

	def __init__(self, team_id: str, credentials: Optional[dict] = None):
		super().__init__(team_id=team_id, credentials=credentials)
		self.webhook_urls = credentials.get("webhook_urls", []) if credentials else []
		self.event_filters = credentials.get("event_filters", {}) if credentials else {}

	def can_handle(self, event: GraphEvent) -> bool:
		"""Handle any event if configured."""
		if not self.webhook_urls:
			return False
		
		# If event filters are specified, only handle matching events
		if self.event_filters:
			return event.event_type in self.event_filters.get("include_event_types", [])
		
		# Otherwise handle all events
		return True

	def execute(self, task: Any, event: GraphEvent) -> ConnectorResult:
		"""POST to all configured webhooks."""
		if not self.webhook_urls:
			return ConnectorResult(
				success=False,
				external_id=None,
				message="No webhook URLs configured"
			)

		payload = self._build_payload(task, event)
		results = []

		for webhook_url in self.webhook_urls:
			# Idempotency check
			idempotency_key = _get_idempotency_key(task.id, event.event_type, webhook_url)
			if _already_fired(idempotency_key):
				results.append((webhook_url, "already_fired"))
				continue

			try:
				import requests
				response = requests.post(
					webhook_url,
					json=payload,
					headers={"Content-Type": "application/json"},
					timeout=10
				)
				
				if response.status_code in (200, 201, 202):
					_mark_fired(idempotency_key)
					results.append((webhook_url, "success"))
				else:
					results.append((webhook_url, f"error_{response.status_code}"))
			except Exception as e:
				results.append((webhook_url, f"exception: {str(e)}"))

		# Determine overall success
		all_success = all(status in ("success", "already_fired") for _, status in results)
		
		return ConnectorResult(
			success=all_success,
			external_id=",".join(status for _, status in results),
			message=f"Posted to {len([s for _, s in results if s == 'success'])} webhooks"
		)

	def _build_payload(self, task: Any, event: GraphEvent) -> dict:
		"""Build the webhook request payload."""
		return {
			"event_type": event.event_type,
			"timestamp": datetime.utcnow().isoformat(),
			"team_id": event.team_id,
			"task": {
				"id": task.id,
				"title": task.title,
				"owner": task.owner,
				"deadline": task.deadline.isoformat() if hasattr(task.deadline, 'isoformat') else str(task.deadline),
				"status": task.status.value if hasattr(task.status, 'value') else str(task.status),
			},
			"metadata": event.metadata,
		}

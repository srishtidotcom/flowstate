"""Connector registry and dispatch logic."""

from typing import Any, Dict, List
from flowstate.connectors.base import BaseConnector, ConnectorResult, GraphEvent
from flowstate.infra import get_db_session
from flowstate.infra.models import ConnectorRun
import json
from datetime import datetime

# In-memory registry: team_id → list of connectors
_registry: Dict[str, List[BaseConnector]] = {}


def register_connector(connector: BaseConnector):
	"""Register a connector for a team."""
	_registry.setdefault(connector.team_id, []).append(connector)


def get_connectors_for_team(team_id: str) -> List[BaseConnector]:
	"""Get all registered connectors for a team."""
	return _registry.get(team_id, [])


def dispatch_event(task: Any, event: GraphEvent) -> List[ConnectorResult]:
	"""
	Find all connectors that can handle this event and execute them.
	Returns list of results from each connector.
	"""
	connectors = get_connectors_for_team(event.team_id)
	results: List[ConnectorResult] = []
	
	for connector in connectors:
		if connector.can_handle(event):
			try:
				result = connector.execute(task, event)
				_log_connector_run(connector.name, task.id, result)
				results.append(result)
			except Exception as e:
				result = ConnectorResult(
					success=False,
					external_id=None,
					message=f"Error executing {connector.name}: {str(e)}"
				)
				_log_connector_run(connector.name, task.id, result)
				results.append(result)
	
	return results


def _log_connector_run(
	connector_name: str,
	task_id: str,
	result: ConnectorResult
):
	"""Log a connector execution attempt to the database."""
	try:
		with get_db_session() as db:
			run = ConnectorRun(
				connector_name=connector_name,
				task_id=task_id,
				status="success" if result.success else "failed",
				ran_at=datetime.utcnow(),
				result=result.message,
			)
			db.add(run)
			db.commit()
	except Exception as e:
		print(f"[connector_registry] Failed to log run for {connector_name}: {e}")

"""Connectors provide actions that Flowstate can take on external systems."""

from flowstate.connectors.base import BaseConnector, ConnectorResult, GraphEvent
from flowstate.connectors.registry import (
	dispatch_event,
	get_connectors_for_team,
	register_connector,
)
from flowstate.connectors.google_calendar import GoogleCalendarConnector
from flowstate.connectors.slack import SlackConnector
from flowstate.connectors.webhook import WebhookConnector
from flowstate.connectors.whatsapp import WhatsAppConnector

__all__ = [
	"BaseConnector",
	"ConnectorResult",
	"GraphEvent",
	"dispatch_event",
	"get_connectors_for_team",
	"register_connector",
	"GoogleCalendarConnector",
	"SlackConnector",
	"WebhookConnector",
	"WhatsAppConnector",
]

"""
Example connector usage patterns.

This module shows how to initialize and use connectors in your application.
"""

from flowstate.connectors import (
	GoogleCalendarConnector,
	SlackConnector,
	WebhookConnector,
	WhatsAppConnector,
	register_connector,
	dispatch_event,
	GraphEvent,
)


def setup_connectors_for_team(team_id: str, config: dict):
	"""
	Initialize and register all connectors for a team based on configuration.
	
	Example:
		config = {
			"google_calendar": {
				"credentials": {"service_account_file": "path/to/service-account.json"}
			},
			"slack": {
				"credentials": {
					"webhook_url": "https://hooks.slack.com/services/...",
					"user_id_map": {"Alice": "@alice", "Bob": "@bob"},
				}
			},
			"webhook": {
				"credentials": {
					"webhook_urls": ["https://example.com/flow-webhook"],
					"event_filters": {
						"include_event_types": ["task_blocked", "deadline_approaching"]
					}
				}
			},
			"whatsapp": {
				"credentials": {
					"phone_number_id": "123456789",
					"access_token": "your_wa_business_token",
					"recipient_map": {"Alice": "+1234567890", "Bob": "+1987654321"},
				}
			},
		}
	"""
	
	# Google Calendar
	if "google_calendar" in config:
		creds = config["google_calendar"].get("credentials", {})
		connector = GoogleCalendarConnector(team_id=team_id, credentials=creds)
		register_connector(connector)
	
	# Slack
	if "slack" in config:
		creds = config["slack"].get("credentials", {})
		connector = SlackConnector(team_id=team_id, credentials=creds)
		register_connector(connector)
	
	# Generic Webhook
	if "webhook" in config:
		creds = config["webhook"].get("credentials", {})
		connector = WebhookConnector(team_id=team_id, credentials=creds)
		register_connector(connector)
	
	# WhatsApp
	if "whatsapp" in config:
		creds = config["whatsapp"].get("credentials", {})
		connector = WhatsAppConnector(team_id=team_id, credentials=creds)
		register_connector(connector)


def emit_task_event(task, event_type: str, metadata: dict, team_id: str):
	"""
	Emit a task event and dispatch to all interested connectors.
	
	Example:
		emit_task_event(
			task=my_task,
			event_type="deadline_approaching",
			metadata={"hours_remaining": 2},
			team_id="team_alpha"
		)
	"""
	event = GraphEvent(
		event_type=event_type,
		task_id=task.id,
		team_id=team_id,
		metadata=metadata,
	)
	
	results = dispatch_event(task, event)
	
	for result in results:
		if result.success:
			print(f"✓ {result.message}")
		else:
			print(f"✗ {result.message}")
	
	return results


# Example event types and when to emit them:
#
# "deadline_approaching" - Task deadline is within 24 hours
#   Metadata: {"hours_remaining": 12}
#
# "task_blocked" - Task is waiting on another task
#   Metadata: {"blocker_title": "...", "blocker_owner": "..."}
#
# "blocker_resolved" - A task that was blocking this one just moved to done
#   Metadata: {"was_blocked_by": "..."}
#
# "nudge" - Gentle reminder to unblock a stalled task
#   Metadata: {"blocked_by": "...", "blocker_owner": "...", "days_stuck": 3, "recipient_phone": "+1234567890"}
#
# "digest" - Daily/weekly summary
#   Metadata: {"total_tasks": 42, "critical_count": 3}

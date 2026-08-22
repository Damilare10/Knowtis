"""
AI Tool definitions and execution engine for Knowtis.
Uses a tag-based action system: the LLM outputs [ACTION:tool_name]{...json...}[/ACTION]
which the backend parses, executes, and returns results to the conversation.
"""
import json
import logging
from typing import Dict, List, Optional, Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import AcademicEvent, Reminder, NotificationInbox
from app.services.reminder_service import ReminderService

logger = logging.getLogger(__name__)

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "set_reminder",
            "description": "Create a reminder for an academic event. Use this when the student asks to be reminded about a deadline, exam, assignment, or any upcoming event.",
            "parameters": {
                "type": "object",
                "properties": {
                    "event_id": {"type": "string", "description": "The UUID of the event to set a reminder for"},
                    "days_before": {"type": "integer", "description": "Number of days before the event to send the reminder (default 1)"},
                },
                "required": ["event_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "dismiss_alert",
            "description": "Dismiss / mark as done a notification alert. Use when the student says they've handled or acknowledged something.",
            "parameters": {
                "type": "object",
                "properties": {
                    "notification_id": {"type": "string", "description": "The UUID of the notification to dismiss"},
                },
                "required": ["notification_id"],
            },
        },
    },
]


ACTION_TAG_RE = __import__("re").compile(r"\[ACTION:(\w+)\](.*?)\[/ACTION\]", __import__("re").DOTALL)

TOOL_SYSTEM_PROMPT = """
## ACTIONS YOU CAN PERFORM

You have access to the following actions. When the student asks for something you can do, use the action format:

[ACTION:set_reminder]
{"event_id": "<uuid>", "days_before": <number>}
[/ACTION]

[ACTION:dismiss_alert]
{"notification_id": "<uuid>"}
[/ACTION]

Rules for using actions:
- Use [ACTION:tool_name] ONLY for tool calls. Put the action tag on its own line.
- Include the JSON parameters exactly between the [ACTION] tags.
- When you use an action, do NOT also write a conversational answer — just output the action tag(s) and nothing else. The system will confirm the action was performed.
- You can request multiple actions at once by outputting multiple [ACTION] blocks.
- Only use the tools listed above. Do not invent new tool names.
- If the student's request cannot be fulfilled with the available tools, explain why and suggest alternatives.

Example — student says: "Remind me about the CSC301 assignment 3 days before it's due"
Your output:
[ACTION:set_reminder]
{"event_id": "abc-123-def", "days_before": 3}
[/ACTION]
"""


class AIToolEngine:
    """Parses ACTION tags from LLM output, executes tools, returns results."""

    @staticmethod
    def parse_actions(text: str) -> List[Dict[str, Any]]:
        """Extract [ACTION:...] blocks from text."""
        for match in ACTION_TAG_RE.finditer(text):
            name = match.group(1)
            try:
                params = json.loads(match.group(2))
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse action params for {name}: {match.group(2)[:100]}")
                continue
            yield {"name": name, "params": params, "raw": match.group(0)}

    @staticmethod
    def has_actions(text: str) -> bool:
        return bool(ACTION_TAG_RE.search(text))

    @staticmethod
    def strip_actions(text: str) -> str:
        return ACTION_TAG_RE.sub("", text).strip()

    @staticmethod
    def execute_action(
        name: str,
        params: Dict[str, Any],
        user_id: UUID,
        db: Session,
    ) -> Dict[str, Any]:
        """Execute a tool and return the result."""
        if name == "set_reminder":
            return AIToolEngine._execute_set_reminder(params, user_id, db)
        elif name == "dismiss_alert":
            return AIToolEngine._execute_dismiss_alert(params, user_id, db)
        else:
            return {"success": False, "error": f"Unknown tool: {name}"}

    @staticmethod
    def _execute_set_reminder(params: Dict, user_id: UUID, db: Session) -> Dict:
        event_id_str = params.get("event_id")
        days_before = int(params.get("days_before", 1))

        if not event_id_str:
            return {"success": False, "error": "Missing event_id"}

        try:
            event_uuid = UUID(event_id_str)
        except (ValueError, TypeError):
            return {"success": False, "error": f"Invalid event_id: {event_id_str}"}

        event = db.query(AcademicEvent).filter(
            AcademicEvent.id == event_uuid,
            AcademicEvent.user_id == user_id,
            AcademicEvent.is_archived == False,
        ).first()

        if not event:
            return {"success": False, "error": "Event not found or not yours"}

        existing = db.query(Reminder).filter(
            Reminder.user_id == user_id,
            Reminder.event_id == event_uuid,
            Reminder.is_active == True,
        ).first()

        if existing:
            return {
                "success": True,
                "already_exists": True,
                "message": f"Reminder for '{event.title}' was already active (scheduled for {existing.scheduled_time.isoformat() if existing.scheduled_time else 'soon'}).",
                "event": {"id": str(event.id), "title": event.title, "course_code": event.course_code},
            }

        reminder = ReminderService.create_reminder(
            user_id=event.user_id,
            event_id=event_uuid,
            days_before=max(1, days_before),
            db=db,
        )

        if reminder:
            return {
                "success": True,
                "message": f"Reminder set for '{event.title}' {days_before} day(s) before {event.date_time.strftime('%b %d, %H:%M') if event.date_time else 'the date'}.",
                "event": {"id": str(event.id), "title": event.title, "course_code": event.course_code},
                "reminder_id": str(reminder.id),
            }
        else:
            return {"success": False, "error": f"Could not create reminder for event. The event may not have a scheduled date."}

    @staticmethod
    def _execute_dismiss_alert(params: Dict, user_id: UUID, db: Session) -> Dict:
        notification_id_str = params.get("notification_id")

        if not notification_id_str:
            return {"success": False, "error": "Missing notification_id"}

        try:
            notif_uuid = UUID(notification_id_str)
        except (ValueError, TypeError):
            return {"success": False, "error": f"Invalid notification_id: {notification_id_str}"}

        notification = db.query(NotificationInbox).filter(
            NotificationInbox.id == notif_uuid,
            NotificationInbox.user_id == user_id,
        ).first()

        if not notification:
            return {"success": False, "error": "Notification not found or not yours"}

        notification.is_read = True
        notification.read_at = __import__("datetime").datetime.utcnow()
        db.commit()

        return {
            "success": True,
            "message": f"Notification '{notification.title or 'Alert'}' dismissed.",
            "notification": {"id": str(notification.id), "title": notification.title},
        }

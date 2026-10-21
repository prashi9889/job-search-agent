"""Put interview and assessment dates found in email on the calendar."""

from __future__ import annotations

import hashlib
from datetime import timedelta
from typing import Protocol

from .audit import AuditLog
from .config import Settings
from .emails import EmailMessage, ProposedDate


class CalendarClient(Protocol):
    def find_by_key(self, key: str) -> dict | None: ...
    def insert(self, event: dict) -> str: ...


def event_key(msg: EmailMessage, proposed: ProposedDate) -> str:
    return hashlib.sha256(f"{msg.id}|{proposed.start.isoformat()}".encode()).hexdigest()[:20]


def build_event(msg: EmailMessage, proposed: ProposedDate, settings: Settings, key: str) -> dict:
    end = proposed.start + timedelta(minutes=settings.event_minutes)
    label = "Interview" if proposed.category.value == "interview" else "Assessment"
    notes = f" ({', '.join(proposed.notes)})" if proposed.notes else ""
    return {
        "summary": f"{label}: {msg.subject}"[:200],
        "description": (
            "Added automatically by Job Search Agent from an email. "
            f"Check the time against the original message{notes}.\n\n"
            f"From: {msg.sender}\n"
            f"Email: https://mail.google.com/mail/u/0/#all/{msg.id}\n\n"
            f"Matched text: {proposed.source_text}"
        ),
        "start": {"dateTime": proposed.start.isoformat()},
        "end": {"dateTime": end.isoformat()},
        "reminders": {"useDefault": False, "overrides": [
            {"method": "popup", "minutes": 24 * 60},
            {"method": "popup", "minutes": 60},
        ]},
        "extendedProperties": {"private": {"jobagent_key": key, "jobagent_message": msg.id}},
    }


def schedule(
    msg: EmailMessage,
    proposed: ProposedDate,
    client: CalendarClient,
    settings: Settings,
    audit: AuditLog,
) -> str:
    """Returns "created", "duplicate" or "needs_review"."""
    subject = f"email:{msg.id}"
    details = {"start": proposed.start.isoformat(), "category": proposed.category.value, "notes": proposed.notes}
    if not (settings.auto_calendar and proposed.confident):
        audit.record("calendar.proposed", subject, details)
        return "needs_review"
    key = event_key(msg, proposed)
    if client.find_by_key(key):
        audit.record("calendar.duplicate", subject, details)
        return "duplicate"
    event_id = client.insert(build_event(msg, proposed, settings, key))
    audit.record("calendar.event_created", subject, {**details, "event_id": event_id})
    return "created"

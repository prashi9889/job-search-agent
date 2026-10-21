"""Read recent job emails and act on the dates they contain."""

from __future__ import annotations

from collections import Counter

from .audit import AuditLog
from .calendar_sync import CalendarClient, schedule
from .config import Settings
from .emails import SCHEDULABLE, EmailMessage, classify, extract_dates


def sync_email(
    messages: list[EmailMessage],
    calendar: CalendarClient,
    settings: Settings,
    audit: AuditLog,
) -> Counter:
    results: Counter = Counter()
    for msg in messages:
        # Each message is handled once; later runs see it again within --days.
        if audit.has("email.classified", f"email:{msg.id}"):
            results["already_seen"] += 1
            continue
        category = classify(msg)
        results[category.value] += 1
        if category.value == "other":
            continue
        # Body text stays out of the audit log; the message id is enough to find it.
        audit.record("email.classified", f"email:{msg.id}", {"category": category.value, "from": msg.sender})
        if category not in SCHEDULABLE:
            continue
        for proposed in extract_dates(msg, category):
            results[schedule(msg, proposed, calendar, settings, audit)] += 1
    return results

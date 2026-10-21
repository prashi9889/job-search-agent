from datetime import datetime, timedelta, timezone

import pytest

from jobagent.audit import AuditLog
from jobagent.config import Settings
from jobagent.emails import Category, EmailMessage, classify, extract_dates
from jobagent.sync import sync_email

IST = timezone(timedelta(hours=5, minutes=30))
RECEIVED = datetime(2026, 10, 21, 10, 0, tzinfo=IST)


def msg(body, subject="Next steps", id="m1", received=RECEIVED):
    return EmailMessage(id=id, sender="hr@acme.example", subject=subject, body=body, received_at=received)


class FakeCalendar:
    def __init__(self):
        self.events = []

    def find_by_key(self, key):
        return next((e for e in self.events if e["extendedProperties"]["private"]["jobagent_key"] == key), None)

    def insert(self, event):
        self.events.append(event)
        return f"evt{len(self.events)}"


@pytest.fixture
def audit(tmp_path):
    log = AuditLog(tmp_path / "audit.db")
    yield log
    log.close()


@pytest.mark.parametrize("body,expected", [
    ("We would like to invite you to an interview.", Category.INTERVIEW),
    ("Please complete the HackerRank coding challenge.", Category.ASSESSMENT),
    ("Thank you for your application to Acme.", Category.CONFIRMATION),
    ("Unfortunately we will not be moving forward. The interview panel...", Category.REJECTION),
    ("We are pleased to extend an offer.", Category.OFFER),
    ("Your weekly newsletter", Category.OTHER),
])
def test_classify(body, expected):
    assert classify(msg(body)) is expected


def test_extract_date_with_time():
    [d] = extract_dates(msg("Your interview is on October 28 at 3:30 PM. Please join on time."))
    assert d.start == datetime(2026, 10, 28, 15, 30, tzinfo=IST)
    assert d.confident


def test_extract_date_formats():
    starts = [d.start for d in extract_dates(msg(
        "Round one: 2026-11-02 14:00.\nRound two: 5th November 10am."
    ))]
    assert starts == [datetime(2026, 11, 2, 14, 0, tzinfo=IST), datetime(2026, 11, 5, 10, 0, tzinfo=IST)]


def test_date_without_time_is_not_confident():
    [d] = extract_dates(msg("The interview will be on Nov 3."))
    assert not d.confident and "no time given" in d.notes


def test_past_dates_ignored_and_year_rolled():
    december = datetime(2026, 12, 20, 9, 0, tzinfo=IST)
    [d] = extract_dates(msg("Interview on January 6 at 11am.", received=december))
    assert d.start.year == 2027
    assert extract_dates(msg("You applied on October 1, 2026 at 9am.")) == []


def test_sync_creates_event_once(audit):
    cal = FakeCalendar()
    inbox = [msg("Your interview is scheduled for October 28 at 3:30 PM IST.", subject="Interview with Acme")]
    assert sync_email(inbox, cal, Settings(), audit)["created"] == 1
    event = cal.events[0]
    assert event["summary"] == "Interview: Interview with Acme"
    assert event["start"]["dateTime"] == "2026-10-28T15:30:00+05:30"
    assert event["end"]["dateTime"] == "2026-10-28T16:30:00+05:30"

    again = sync_email(inbox, cal, Settings(), audit)
    assert again["already_seen"] == 1 and len(cal.events) == 1


def test_uncertain_or_disabled_goes_to_review(audit):
    cal = FakeCalendar()
    r = sync_email([msg("Interview on Nov 3.")], cal, Settings(), audit)
    assert r["needs_review"] == 1 and cal.events == []
    r = sync_email([msg("Interview on Nov 3 at 2pm.", id="m2")], cal, Settings(auto_calendar=False), audit)
    assert r["needs_review"] == 1 and cal.events == []
    assert [e["action"] for e in audit.recent()].count("calendar.proposed") == 2


def test_rejection_and_other_never_scheduled(audit):
    cal = FakeCalendar()
    sync_email([
        msg("Unfortunately we decided to move forward with other candidates. Interview on Nov 3 at 2pm.", id="r"),
        msg("Sale ends November 3 at 2pm!", subject="Deals", id="o"),
    ], cal, Settings(), audit)
    assert cal.events == []
    # Unrelated mail is not written to the audit log at all.
    assert not audit.has("email.classified", "email:o")

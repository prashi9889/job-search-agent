"""Classify job-related emails and pull out proposed dates.

Email content is untrusted: it is only matched against patterns here, never
treated as instructions, and it is processed locally (decision D2).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from dateutil import parser as dateparser


@dataclass
class EmailMessage:
    id: str
    sender: str
    subject: str
    body: str
    received_at: datetime  # timezone-aware
    thread_id: str = ""


class Category(str, Enum):
    OFFER = "offer"
    REJECTION = "rejection"
    INTERVIEW = "interview"
    ASSESSMENT = "assessment"
    CONFIRMATION = "confirmation"
    RECRUITER = "recruiter"
    OTHER = "other"


# Checked in order; the first category with a matching pattern wins.
_RULES: list[tuple[Category, re.Pattern]] = [
    (Category.REJECTION, re.compile(
        r"unfortunately|not (?:be )?moving forward|decided to (?:proceed|move forward) with other|"
        r"no longer (?:being )?considered|regret to inform|position has been filled", re.I)),
    (Category.OFFER, re.compile(r"\boffer letter\b|pleased to (?:extend|offer)|job offer|offer of employment", re.I)),
    (Category.INTERVIEW, re.compile(
        r"\binterview\b|phone screen|video call|meet the team|onsite visit|schedul\w+ (?:a )?(?:call|chat|meeting)", re.I)),
    (Category.ASSESSMENT, re.compile(
        r"assessment|coding (?:challenge|test|exercise)|take[- ]home|hackerrank|codility|online test", re.I)),
    (Category.CONFIRMATION, re.compile(
        r"(?:received|thank you for) (?:your )?(?:job )?application|application (?:was )?(?:received|submitted)", re.I)),
    (Category.RECRUITER, re.compile(r"recruit|talent acquisition|opportunity|your profile|hiring", re.I)),
]

SCHEDULABLE = {Category.INTERVIEW, Category.ASSESSMENT}


def classify(msg: EmailMessage) -> Category:
    text = f"{msg.subject}\n{msg.body}"
    for category, pattern in _RULES:
        if pattern.search(text):
            return category
    return Category.OTHER


_MONTH = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?"
_DATE = re.compile(
    rf"\b\d{{4}}-\d{{2}}-\d{{2}}\b"
    rf"|\b{_MONTH}\s+\d{{1,2}}(?:st|nd|rd|th)?(?:,?\s+\d{{4}})?\b"
    rf"|\b\d{{1,2}}(?:st|nd|rd|th)?\s+(?:of\s+)?{_MONTH}(?:,?\s+\d{{4}})?\b",
    re.I,
)
_YEAR = re.compile(r"\b\d{4}\b")
_TIME = re.compile(r"\b\d{1,2}(?::\d{2})?\s*(?:am|pm|a\.m\.|p\.m\.)|\b(?:[01]?\d|2[0-3]):[0-5]\d\b", re.I)
_SENTENCE = re.compile(r"(?<=[.!?])\s+|\n+")


@dataclass
class ProposedDate:
    start: datetime
    has_time: bool
    source_text: str
    category: Category
    notes: list[str] = field(default_factory=list)

    @property
    def confident(self) -> bool:
        return self.has_time


def extract_dates(msg: EmailMessage, category: Category | None = None) -> list[ProposedDate]:
    """Find explicit future dates in the email, one per sentence."""
    category = category or classify(msg)
    found: list[ProposedDate] = []
    for sentence in _SENTENCE.split(msg.body):
        date_m = _DATE.search(sentence)
        if not date_m:
            continue
        time_m = _TIME.search(sentence)
        text = date_m.group(0) + (" " + time_m.group(0).replace(".", "") if time_m else " 09:00")
        default = msg.received_at.replace(hour=0, minute=0, second=0, microsecond=0)
        try:
            start = dateparser.parse(text, default=default, dayfirst=False)
        except (ValueError, OverflowError):
            continue
        if start.tzinfo is None:
            start = start.replace(tzinfo=msg.received_at.tzinfo)
        notes = []
        # "March 3" in a December email means next year.
        if start < msg.received_at and not _YEAR.search(date_m.group(0)):
            start = start.replace(year=start.year + 1)
            notes.append("year inferred")
        if start < msg.received_at:
            continue
        if not time_m:
            notes.append("no time given")
        found.append(ProposedDate(start, bool(time_m), sentence.strip()[:300], category, notes))
    return found

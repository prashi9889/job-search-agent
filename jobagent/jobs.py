"""Local job store with duplicate detection and relevance filtering."""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .profile import SearchPreferences


@dataclass
class Job:
    source: str
    company: str
    title: str
    location: str
    url: str
    posted: str = ""
    description: str = ""

    @property
    def key(self) -> str:
        """Same role at the same company and place counts as one job, whatever the source."""
        norm = lambda s: re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()
        return "|".join((norm(self.company), norm(self.title), norm(self.location.split(",")[0])))


# Words that make a title relevant even if it is not an exact target role.
QS_TERMS = re.compile(
    r"quantity survey|\bqs\b|billing engineer|estimat|cost (?:manager|consultant|engineer)|"
    r"commercial (?:manager|executive)|contracts? (?:engineer|administrator)|quantity take", re.I)


def relevance(job: Job, prefs: SearchPreferences) -> str | None:
    """None if the job is relevant, otherwise the reason it was filtered out."""
    kw = prefs.excluded_by(job.company, job.title, job.description)
    if kw:
        return f"excluded keyword: {kw}"
    for word in prefs.exclude_title_words:
        if re.search(rf"\b{re.escape(word)}\b", job.title, re.I):
            return f"title too senior: {word}"
    if not (QS_TERMS.search(job.title)
            or any(r.lower() in job.title.lower() for r in prefs.target_roles)):
        return "title not a QS role"
    countries = [l.split("(")[0].strip().lower() for l in prefs.locations]
    if countries and "anywhere" not in countries and job.location:
        if not any(c in job.location.lower() for c in countries) and not _in_india(job.location, countries):
            return f"location: {job.location}"
    return None


_INDIAN_PLACES = re.compile(
    r"\b(?:ind|india|mumbai|delhi|new delhi|gurgaon|gurugram|noida|bengaluru|bangalore|hyderabad|chennai|"
    r"pune|kolkata|ahmedabad|kochi|jaipur|lucknow|chandigarh|navi mumbai|thane|coimbatore|visakhapatnam|"
    r"telangana|maharashtra|karnataka|tamil nadu|haryana|uttar pradesh|gujarat|kerala|west bengal)\b", re.I)


def _in_india(location: str, countries: list[str]) -> bool:
    return "india" in countries and bool(_INDIAN_PLACES.search(location))


SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    key         TEXT PRIMARY KEY,
    source      TEXT NOT NULL,
    company     TEXT NOT NULL,
    title       TEXT NOT NULL,
    location    TEXT NOT NULL,
    url         TEXT NOT NULL,
    posted      TEXT NOT NULL,
    first_seen  TEXT NOT NULL,
    stage       TEXT NOT NULL DEFAULT 'discovered',
    filtered    TEXT
);
"""


class JobStore:
    def __init__(self, path: Path):
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)

    def add(self, job: Job, filtered: str | None) -> bool:
        """Store a job; False if it was already known (from any source)."""
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self._conn:
            cur = self._conn.execute(
                "INSERT OR IGNORE INTO jobs (key, source, company, title, location, url, posted, first_seen, filtered)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (job.key, job.source, job.company, job.title, job.location, job.url, job.posted, now, filtered),
            )
        return cur.rowcount == 1

    def shortlist(self, limit: int = 100) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM jobs WHERE filtered IS NULL ORDER BY first_seen DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    def counts(self) -> dict:
        row = self._conn.execute(
            "SELECT COUNT(*) AS total, SUM(filtered IS NULL) AS relevant FROM jobs"
        ).fetchone()
        return {"total": row["total"], "relevant": row["relevant"] or 0}

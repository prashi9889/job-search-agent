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
    if countries and "anywhere" not in countries and job.location and not _MULTI.match(job.location):
        if not any(_in_country(job.location, c) for c in countries):
            return f"location: {job.location}"
    return None


# Workday shows "2 Locations" when a role is in several places; keep those for review.
_MULTI = re.compile(r"^\s*\d+\s+locations?\s*$", re.I)

# Country names, codes and main cities as they appear in job listings.
PLACES = {
    "india": r"india|\bind\b|mumbai|delhi|gurgaon|gurugram|noida|bengaluru|bangalore|hyderabad|chennai|pune|"
             r"kolkata|ahmedabad|kochi|jaipur|lucknow|chandigarh|thane|coimbatore|visakhapatnam|telangana|"
             r"maharashtra|karnataka|tamil nadu|haryana|uttar pradesh|gujarat|kerala|west bengal",
    "united arab emirates": r"united arab emirates|\buae\b|(?-i:\bARE\b)|dubai|abu dhabi|sharjah|ajman|ras al khaimah",
    "qatar": r"qatar|\bqat\b|doha|lusail",
    "saudi arabia": r"saudi|\bksa\b|\bsau\b|riyadh|jeddah|dammam|khobar|neom|mecca|makkah|medina",
    "oman": r"\boman\b|\bomn\b|muscat|sohar|duqm",
    "kuwait": r"kuwait|\bkwt\b",
    "bahrain": r"bahrain|\bbhr\b|manama",
    "united kingdom": r"united kingdom|\buk\b|\bgbr?\b|england|scotland|wales|northern ireland|london|"
                      r"manchester|birmingham|leeds|bristol|glasgow|edinburgh|liverpool|cardiff|belfast|"
                      r"newcastle|sheffield|nottingham",
}


def _in_country(location: str, country: str) -> bool:
    pattern = PLACES.get(country)
    if pattern:
        return re.search(pattern, location, re.I) is not None
    return country in location.lower()


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

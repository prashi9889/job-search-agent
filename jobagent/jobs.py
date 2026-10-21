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


NO_SPONSORSHIP = re.compile(
    r"(?:unable|not able|cannot|can't|do not|don't|will not|won't|not) (?:currently )?(?:to )?"
    r"(?:offer|provide|support)?\s*(?:visa )?sponsor"
    r"|no (?:visa )?sponsorship|not eligible for sponsorship|without the need for sponsorship"
    r"|must have (?:the |a )?(?:full |permanent )?right to work"
    r"|(?:uae|gcc|saudi|qatar) nationals? only|locals? only", re.I)


def relevance(job: Job, prefs: SearchPreferences) -> str | None:
    """None if the job is relevant, otherwise the reason it was filtered out."""
    kw = prefs.excluded_by(job.company, job.title, job.description)
    if kw:
        return f"excluded keyword: {kw}"
    if prefs.needs_visa_sponsorship and NO_SPONSORSHIP.search(f"{job.title} {job.description}"):
        return "no visa sponsorship"
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


_COMPANY_SUFFIXES = re.compile(
    r"\b(?:consult(?:ing|ants?|ancy)?|llc|l l c|ltd|limited|pvt|private|inc|co|company|group|fze|fzco|plc)\b")


def company_name(name: str) -> str:
    """'D&A Consulting LLC' and 'D&A Consult' compare equal."""
    s = re.sub(r"[^a-z0-9&]+", " ", name.lower())
    return re.sub(r"\s+", " ", _COMPANY_SUFFIXES.sub(" ", s)).strip()


# Columns added after the first release; created on existing databases too.
EXTRA_COLUMNS = {"decided_at": "TEXT", "applied_at": "TEXT", "resume_version": "TEXT"}

# What each button on the dashboard does to a job's stage.
DECISIONS = {"accept": "approved", "skip": "skipped", "applied": "applied", "undo": "discovered"}
OPEN_STAGES = ("discovered", "approved")


class DuplicateApplication(Exception):
    pass


class JobStore:
    def __init__(self, path: Path):
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)
        have = {r["name"] for r in self._conn.execute("PRAGMA table_info(jobs)")}
        for col, kind in EXTRA_COLUMNS.items():
            if col not in have:
                self._conn.execute(f"ALTER TABLE jobs ADD COLUMN {col} {kind}")

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

    def shortlist(self, limit: int = 100, stages: tuple[str, ...] = OPEN_STAGES) -> list[dict]:
        marks = ",".join("?" * len(stages))
        rows = self._conn.execute(
            f"SELECT rowid AS id, * FROM jobs WHERE filtered IS NULL AND stage IN ({marks})"
            " ORDER BY first_seen DESC LIMIT ?", (*stages, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def get(self, job_id: int) -> dict | None:
        row = self._conn.execute("SELECT rowid AS id, * FROM jobs WHERE rowid = ?", (job_id,)).fetchone()
        return dict(row) if row else None

    def already_applied(self, job: dict) -> dict | None:
        """Another job at the same company with the same title that is approved or applied."""
        norm = lambda s: re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()
        for row in self._conn.execute(
            "SELECT rowid AS id, * FROM jobs WHERE stage IN ('approved', 'applied') AND rowid != ?", (job["id"],)
        ):
            if company_name(row["company"]) == company_name(job["company"]) and norm(row["title"]) == norm(job["title"]):
                return dict(row)
        return None

    def decide(self, job_id: int, decision: str, resume_version: str | None = None) -> dict:
        job = self.get(job_id)
        if job is None:
            raise KeyError(job_id)
        stage = DECISIONS[decision]
        if decision == "accept":
            dup = self.already_applied(job)
            if dup:
                raise DuplicateApplication(f"Already {dup['stage']}: {dup['title']} at {dup['company']}")
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self._conn:
            self._conn.execute(
                "UPDATE jobs SET stage = ?, decided_at = ?,"
                " applied_at = CASE WHEN ? = 'applied' THEN ? ELSE applied_at END,"
                " resume_version = COALESCE(?, resume_version) WHERE rowid = ?",
                (stage, now, stage, now, resume_version, job_id),
            )
        return self.get(job_id)

    def counts(self) -> dict:
        row = self._conn.execute(
            "SELECT COUNT(*) AS total, SUM(filtered IS NULL) AS relevant FROM jobs"
        ).fetchone()
        return {"total": row["total"], "relevant": row["relevant"] or 0}

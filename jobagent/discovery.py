"""Fetch jobs from company career portals and job-alert emails.

Listing text from these sources is untrusted data: it is stored and matched,
never followed as instructions.
"""

from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from collections import Counter
from importlib import resources
from typing import Callable, Iterable

from .audit import AuditLog
from .emails import EmailMessage
from .jobs import Job, JobStore, relevance
from .profile import SearchPreferences

USER_AGENT = "Mozilla/5.0 (personal job search assistant)"
SEARCH_TERMS = ["quantity surveyor", "billing engineer", "estimation engineer", "cost manager"]


def load_sources() -> dict:
    return json.loads(resources.files("jobagent").joinpath("sources.json").read_text())


def _http_json(url: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers={
        "User-Agent": USER_AGENT, "Accept": "application/json", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


Fetch = Callable[[str, dict | None], dict]


def workday(src: dict, term: str, fetch: Fetch = _http_json) -> list[Job]:
    base = f"https://{src['host']}"
    data = fetch(f"{base}/wday/cxs/{src['tenant']}/{src['site']}/jobs",
                 {"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": term})
    return [Job("company:" + src["name"], src["name"], p["title"], p.get("locationsText", ""),
                f"{base}/en-US/{src['site']}{p['externalPath']}", p.get("postedOn", ""))
            for p in data.get("jobPostings", [])]


def smartrecruiters(src: dict, term: str, fetch: Fetch = _http_json) -> list[Job]:
    q = urllib.parse.urlencode({"q": term, "limit": 50})
    data = fetch(f"https://api.smartrecruiters.com/v1/companies/{src['company_id']}/postings?{q}", None)
    jobs = []
    for p in data.get("content", []):
        loc = p.get("location", {})
        place = loc.get("fullLocation") or ", ".join(filter(None, [loc.get("city"), loc.get("region"), loc.get("country")]))
        jobs.append(Job("company:" + src["name"], src["name"], p["name"], place,
                        f"https://jobs.smartrecruiters.com/{src['company_id']}/{p['id']}", p.get("releasedDate", "")))
    return jobs


def oracle(src: dict, term: str, fetch: Fetch = _http_json) -> list[Job]:
    finder = f'findReqs;siteNumber={src["site"]},keyword="{term}",limit=50'
    url = (f"https://{src['host']}/hcmRestApi/resources/latest/recruitingCEJobRequisitions"
           f"?onlyData=true&expand=requisitionList&finder={urllib.parse.quote(finder, safe=';=,')}")
    items = fetch(url, None).get("items", [])
    reqs = items[0].get("requisitionList", []) if items else []
    return [Job("company:" + src["name"], src["name"], r["Title"], r.get("PrimaryLocation", ""),
                f"https://{src['host']}/hcmUI/CandidateExperience/en/sites/{src['site']}/job/{r['Id']}",
                r.get("PostedDate", ""))
            for r in reqs]


FETCHERS = {"workday": workday, "smartrecruiters": smartrecruiters, "oracle": oracle}


def link_sources(sources: dict) -> list[dict]:
    """Career sites without a feed, as ready-to-open search links."""
    q = urllib.parse.quote("quantity surveyor")
    return [{"name": s["name"], "url": s["url"].replace("{q}", q)}
            for s in sources["companies"] if s["type"] == "link"]


def alert_jobs(msg: EmailMessage, sources: dict) -> list[Job]:
    """Jobs listed in a job-alert email from Naukri, LinkedIn, Indeed or Foundit."""
    sender = msg.sender.lower()
    site = next((s for s, domains in sources["job_alert_senders"].items()
                 if any(d in sender for d in domains)), None)
    if not site:
        return []
    pattern = re.compile(sources["job_url_patterns"][site], re.I)
    lines = [l.strip() for l in msg.body.splitlines()]
    jobs, seen, last = [], set(), -1
    for i, line in enumerate(lines):
        m = pattern.search(line)
        if not m:
            continue
        # Alerts list title, company and location on the lines above the link,
        # after the previous job's link.
        block = [l for l in lines[max(last + 1, i - 3):i] if l and not l.startswith("http")]
        last = i
        url = m.group(0).rstrip(").,>\"'")
        if url in seen:
            continue
        seen.add(url)
        inline = line[:m.start()].strip(" :-|")
        if not block and len(inline) > 12:  # "Quantity Surveyor - AECOM: https://..."
            block = [inline]
        if not block:
            continue
        title, company, location = (block + ["", ""])[:3]
        jobs.append(Job(f"alert:{site}", company or "(see listing)", title, location, url))
    return jobs


def discover(
    prefs: SearchPreferences,
    store: JobStore,
    audit: AuditLog,
    emails: Iterable[EmailMessage] = (),
    fetch: Fetch = _http_json,
    sources: dict | None = None,
) -> Counter:
    sources = sources or load_sources()
    results: Counter = Counter()

    def keep(job: Job) -> None:
        if not re.match(r"https?://", job.url, re.I):  # never store javascript: or other schemes
            results["bad_url"] += 1
            return
        reason = relevance(job, prefs)
        if store.add(job, reason):
            results["relevant" if reason is None else "filtered"] += 1
        else:
            results["duplicate"] += 1

    for src in sources["companies"]:
        fetcher = FETCHERS.get(src["type"])
        if not fetcher:
            continue
        for term in SEARCH_TERMS:
            try:
                for job in fetcher(src, term, fetch):
                    keep(job)
            except Exception as exc:  # one broken portal must not stop the rest
                results["errors"] += 1
                audit.record("discovery.error", src["name"], {"term": term, "error": str(exc)[:300]})
                break
    for msg in emails:
        for job in alert_jobs(msg, sources):
            keep(job)
    audit.record("discovery.run", "jobs", dict(results))
    return results

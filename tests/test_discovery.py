from datetime import datetime, timezone

import pytest

from jobagent.audit import AuditLog
from jobagent.discovery import alert_jobs, discover, link_sources, load_sources
from jobagent.emails import EmailMessage
from jobagent.google import html_to_text
from jobagent.jobs import Job, JobStore, relevance
from jobagent.profile import SearchPreferences

PREFS = SearchPreferences(
    target_roles=["Quantity Surveyor", "Billing Engineer", "Estimation Engineer"],
    locations=["India (any city)"],
    exclude_keywords=["UPVC", "windows and doors", "aluminium fabrication"],
    exclude_title_words=["Senior", "Principal", "Lead"],
)
NOW = datetime(2026, 10, 21, tzinfo=timezone.utc)


@pytest.fixture
def store(tmp_path):
    return JobStore(tmp_path / "jobs.db")


@pytest.fixture
def audit(tmp_path):
    return AuditLog(tmp_path / "audit.db")


@pytest.mark.parametrize("title,company,location,expected", [
    ("Quantity Surveyor", "AECOM", "Gurugram, Haryana, India", None),
    ("Billing Engineer", "L&T", "Chennai", None),
    ("Cost Manager", "JLL", "Bengaluru, IND", None),
    ("Principal Quantity Surveyor", "WSP", "Bengaluru, Karnataka, India", "title too senior: Principal"),
    ("Quantity Surveyor", "Fenesta uPVC Windows", "Delhi", "excluded keyword: UPVC"),
    ("Software Engineer", "AECOM", "Pune", "title not a QS role"),
    ("Quantity Surveyor", "JLL", "Singapore", "location: Singapore"),
])
def test_relevance(title, company, location, expected):
    assert relevance(Job("x", company, title, location, "https://e/1"), PREFS) == expected


def test_same_job_from_two_sources_is_one(store):
    a = Job("company:AECOM", "AECOM", "Quantity Surveyor", "Gurugram, Haryana, India", "https://aecom/1")
    b = Job("alert:linkedin", "Aecom", "Quantity  Surveyor", "Gurugram", "https://linkedin/2")
    assert store.add(a, None) and not store.add(b, None)


def fake_fetch(url, body):
    if "myworkdayjobs" in url:
        assert body["searchText"]
        return {"jobPostings": [
            {"title": "Quantity Surveyor", "externalPath": "/job/Mumbai/QS_R1", "locationsText": "Mumbai, India", "postedOn": "Posted Today"},
            {"title": "HR Partner", "externalPath": "/job/Mumbai/HR_R2", "locationsText": "Mumbai, India"},
        ]}
    if "smartrecruiters" in url:
        return {"content": [{"id": "744", "name": "Cost Manager / Quantity Surveyor",
                             "location": {"city": "Hyderabad", "country": "in",
                                          "fullLocation": "Hyderabad, Telangana, India"},
                             "releasedDate": "2026-10-20"}]}
    if "oraclecloud" in url:
        return {"items": [{"requisitionList": [
            {"Id": "99", "Title": "Quantity Surveyor", "PrimaryLocation": "Bengaluru, Karnataka, India", "PostedDate": "2026-10-16"}]}]}
    raise AssertionError(url)


def test_discover_company_portals(store, audit):
    sources = {
        "companies": [
            {"name": "JLL", "type": "workday", "host": "jll.wd1.myworkdayjobs.com", "tenant": "jll", "site": "jllcareers"},
            {"name": "Turner & Townsend", "type": "smartrecruiters", "company_id": "turnertownsend"},
            {"name": "WSP", "type": "oracle", "host": "emit.fa.ca3.oraclecloud.com", "site": "CX_2001"},
            {"name": "AECOM", "type": "link", "url": "https://aecom.jobs/"},
        ],
        "job_alert_senders": {}, "job_url_patterns": {},
    }
    r = discover(PREFS, store, audit, fetch=fake_fetch, sources=sources)
    assert r["relevant"] == 3 and r["filtered"] == 1
    urls = {j["url"] for j in store.shortlist()}
    assert "https://jll.wd1.myworkdayjobs.com/en-US/jllcareers/job/Mumbai/QS_R1" in urls
    assert "https://jobs.smartrecruiters.com/turnertownsend/744" in urls
    assert "https://emit.fa.ca3.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_2001/job/99" in urls


def test_broken_portal_is_logged_not_fatal(store, audit):
    def boom(url, body):
        raise OSError("timeout")
    sources = {"companies": [{"name": "JLL", "type": "workday", "host": "h", "tenant": "t", "site": "s"}],
               "job_alert_senders": {}, "job_url_patterns": {}}
    assert discover(PREFS, store, audit, fetch=boom, sources=sources)["errors"] == 1
    assert audit.recent()[1]["action"] == "discovery.error"


LINKEDIN_ALERT = """Your job alert for quantity surveyor in India
Quantity Surveyor
AECOM
Gurugram, Haryana, India
View job: https://www.linkedin.com/comm/jobs/view/4455624126/?trackingId=abc

Billing Engineer
Larsen & Toubro
Chennai, Tamil Nadu, India
View job: https://www.linkedin.com/comm/jobs/view/4455741185/

See all jobs: https://www.linkedin.com/comm/jobs/search
"""


def test_linkedin_alert_email(store, audit):
    msg = EmailMessage("a1", "LinkedIn Job Alerts <jobalerts-noreply@linkedin.com>", "quantity surveyor", LINKEDIN_ALERT, NOW)
    jobs = alert_jobs(msg, load_sources())
    assert [(j.title, j.company, j.location) for j in jobs] == [
        ("Quantity Surveyor", "AECOM", "Gurugram, Haryana, India"),
        ("Billing Engineer", "Larsen & Toubro", "Chennai, Tamil Nadu, India"),
    ]
    assert discover(PREFS, store, audit, emails=[msg], fetch=fake_fetch,
                    sources={**load_sources(), "companies": []})["relevant"] == 2


def test_naukri_html_alert():
    body = html_to_text(
        '<table><tr><td><a href="https://www.naukri.com/job-listings-quantity-surveyor-tata-projects-hyderabad-1-to-3-years-211026">'
        'Quantity Surveyor</a></td></tr><tr><td>Tata Projects</td></tr><tr><td>Hyderabad</td></tr></table>'
        '<a href="javascript:alert(1)">x</a>')
    msg = EmailMessage("n1", "Naukri <jobalert@naukri.com>", "Jobs for you", body, NOW)
    [job] = alert_jobs(msg, load_sources())
    assert job.title == "Quantity Surveyor" and job.url.startswith("https://www.naukri.com/job-listings-")


def test_other_senders_ignored():
    msg = EmailMessage("x", "promo@shop.example", "Sale", "https://www.linkedin.com/comm/jobs/view/1", NOW)
    assert alert_jobs(msg, load_sources()) == []


def test_link_sources_fill_query():
    links = {l["name"]: l["url"] for l in link_sources(load_sources())}
    assert links["Jacobs"].endswith("keyword=quantity%20surveyor")

import pytest
from fastapi.testclient import TestClient

from jobagent.app import create_app
from jobagent.audit import AuditLog
from jobagent.config import data_dir
from jobagent.jobs import Job, JobStore


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("JOBAGENT_HOME", str(tmp_path / "home"))


@pytest.fixture
def client(tmp_path):
    audit = AuditLog(tmp_path / "audit.db")
    app = create_app(audit)
    store = JobStore(data_dir() / "jobs.db")
    store.add(Job("manual", "D&A Consulting", "Junior Quantity Surveyor", "Dubai", "https://www.founditgulf.com/job/1"), None)
    store.add(Job("alert:linkedin", "D&A Consult", "Junior Quantity Surveyor", "Abu Dhabi", "https://linkedin/2"), None)
    return TestClient(app), audit


H = {"X-Jobagent": "1"}


def test_accept_then_applied(client):
    c, audit = client
    jobs = c.get("/api/jobs").json()
    first = jobs[-1]["id"]
    assert c.post(f"/api/jobs/{first}/decision", json={"decision": "accept"}, headers=H).json()["stage"] == "approved"
    r = c.post(f"/api/jobs/{first}/decision", json={"decision": "applied", "resume_version": "DA_Consult_v1"}, headers=H).json()
    assert r["stage"] == "applied" and r["applied_at"] and r["resume_version"] == "DA_Consult_v1"
    assert "Accept" in c.get("/").text
    assert {"application.accept", "application.applied"} <= {e["action"] for e in audit.recent()}


def test_duplicate_blocked(client):
    c, _ = client
    ids = [j["id"] for j in c.get("/api/jobs").json()]
    store = JobStore(data_dir() / "jobs.db")
    store.add(Job("x", "D&A Consulting", "Junior Quantity Surveyor", "Sharjah", "https://e/3"), None)
    c.post(f"/api/jobs/{ids[-1]}/decision", json={"decision": "accept"}, headers=H)
    third = max(j["id"] for j in c.get("/api/jobs").json())
    r = c.post(f"/api/jobs/{third}/decision", json={"decision": "accept"}, headers=H)
    assert r.status_code == 409 and "Already approved" in r.json()["detail"]


def test_company_name_variants():
    from jobagent.jobs import company_name
    assert company_name("D&A Consulting LLC") == company_name("D&A Consult") == "d&a"
    assert company_name("AECOM") != company_name("Arcadis")


def test_requires_header_and_valid_decision(client):
    c, _ = client
    jid = c.get("/api/jobs").json()[0]["id"]
    assert c.post(f"/api/jobs/{jid}/decision", json={"decision": "accept"}).status_code == 403
    assert c.post(f"/api/jobs/{jid}/decision", json={"decision": "submit"}, headers=H).status_code == 400
    assert c.post("/api/jobs/999/decision", json={"decision": "skip"}, headers=H).status_code == 404


def test_skip_hides_job(client):
    c, _ = client
    jid = c.get("/api/jobs").json()[0]["id"]
    c.post(f"/api/jobs/{jid}/decision", json={"decision": "skip"}, headers=H)
    assert jid not in [j["id"] for j in c.get("/api/jobs").json()]

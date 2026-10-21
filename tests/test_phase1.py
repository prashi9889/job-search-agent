import sqlite3
import stat

import pytest
from fastapi.testclient import TestClient

from jobagent import cli
from jobagent.app import create_app
from jobagent.audit import AuditLog
from jobagent.config import AIMode, Settings, data_dir, load_settings
from jobagent.privacy import PERSONAL, DataClass, PrivacyViolation, Processor, require, route


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("JOBAGENT_HOME", str(tmp_path / "home"))
    return tmp_path / "home"


@pytest.fixture
def audit(tmp_path):
    log = AuditLog(tmp_path / "audit.db")
    yield log
    log.close()


def test_defaults_keep_everything_local():
    settings = Settings()
    assert settings.ai_mode is AIMode.HYBRID
    assert not settings.external_ai_opt_in
    assert all(route(dc, settings) is Processor.LOCAL for dc in DataClass)


@pytest.mark.parametrize("mode", list(AIMode))
@pytest.mark.parametrize("opt_in", [True, False])
def test_personal_data_never_routes_external(mode, opt_in):
    settings = Settings(ai_mode=mode, external_ai_opt_in=opt_in)
    for dc in PERSONAL:
        assert route(dc, settings) is Processor.LOCAL


def test_job_listing_external_only_with_hybrid_opt_in():
    assert route(DataClass.JOB_LISTING, Settings(external_ai_opt_in=True)) is Processor.EXTERNAL
    assert route(DataClass.JOB_LISTING, Settings(ai_mode=AIMode.LOCAL, external_ai_opt_in=True)) is Processor.LOCAL


def test_require_blocks_and_audits(audit):
    with pytest.raises(PrivacyViolation):
        require(DataClass.PROFILE, Processor.EXTERNAL, Settings(external_ai_opt_in=True), audit, "match")
    require(DataClass.JOB_LISTING, Processor.EXTERNAL, Settings(external_ai_opt_in=True), audit, "match")
    actions = [e["action"] for e in audit.recent()]
    assert actions == ["privacy.external_call", "privacy.blocked"]


def test_audit_is_append_only(audit):
    audit.record("x", "y")
    with pytest.raises(sqlite3.IntegrityError):
        audit._conn.execute("UPDATE audit SET action = 'z'")
    with pytest.raises(sqlite3.IntegrityError):
        audit._conn.execute("DELETE FROM audit")


def test_init_and_opt_in_are_recorded(home):
    cli.main(["init"])
    assert stat.S_IMODE(home.stat().st_mode) == 0o700
    assert stat.S_IMODE((home / "settings.json").stat().st_mode) == 0o600
    cli.main(["privacy", "--external-opt-in", "on"])
    assert load_settings().external_ai_opt_in
    actions = [e["action"] for e in AuditLog(data_dir() / "audit.db").recent()]
    assert actions == ["privacy.opt_in_changed", "project.init"]


def test_dashboard_reports_routing(audit):
    client = TestClient(create_app(audit))
    body = client.get("/api/status").json()
    assert body["routing"]["profile"] == "local"
    assert body["integrations"]["gmail"] == "not connected"
    assert client.get("/").status_code == 200

import json
import stat

import pytest

from jobagent import cli
from jobagent.profile import SearchPreferences, load_profile, validate

PROFILE = {
    "contact": {"name": "Test Person"},
    "education": [],
    "experience": [],
    "skills": {},
    "preferences": {
        "target_roles": ["Quantity Surveyor"],
        "locations": ["India"],
        "exclude_keywords": ["UPVC", "windows and doors", "aluminium fabrication"],
    },
}


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("JOBAGENT_HOME", str(tmp_path / "home"))
    return tmp_path / "home"


def test_validate_requires_sections_and_roles():
    assert validate(PROFILE) == []
    assert "missing section: skills" in validate({k: v for k, v in PROFILE.items() if k != "skills"})
    assert "preferences.target_roles is empty" in validate({**PROFILE, "preferences": {}})


def test_import_saves_privately(tmp_path, home):
    src = tmp_path / "p.json"
    src.write_text(json.dumps(PROFILE))
    cli.main(["profile", "import", str(src)])
    assert load_profile() == PROFILE
    assert stat.S_IMODE((home / "profile.json").stat().st_mode) == 0o600


def test_invalid_profile_not_saved(tmp_path):
    src = tmp_path / "p.json"
    src.write_text(json.dumps({"contact": {}}))
    with pytest.raises(SystemExit):
        cli.main(["profile", "import", str(src)])
    assert load_profile() is None


def test_exclusions():
    prefs = SearchPreferences.from_profile(PROFILE)
    assert prefs.excluded_by("Quantity Surveyor", "uPVC Windows Pvt Ltd") == "UPVC"
    assert prefs.excluded_by("Billing Engineer", "We make windows and doors") == "windows and doors"
    # Aluminium formwork on a building site is still a QS job.
    assert prefs.excluded_by("Quantity Surveyor", "Residential towers using aluminium formwork") is None

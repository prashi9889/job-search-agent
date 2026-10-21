from jobagent import schedule
from jobagent.humanize import check
from jobagent.jobs import Job, relevance
from jobagent.profile import SearchPreferences


def test_humanize_flags_stock_phrases_and_dashes():
    kinds = {(f.kind, f.text) for f in check("Spearheaded BOQ work — leveraged Excel.\nPrepared BOQs.")}
    assert ("stock phrase", "spearheaded") in kinds
    assert ("stock phrase", "leveraged") in kinds
    assert ("em dash", "—") in kinds


def test_humanize_passes_plain_text():
    assert check("Prepared BOQ statements from drawings.\nChecked contractor bills before payment.") == []


def test_humanize_repeated_openings():
    text = "\n".join(["Prepared the monthly BOQ report."] * 3)
    assert any(f.kind == "repeated opening" for f in check(text))


def test_sponsorship_filter():
    prefs = SearchPreferences(target_roles=["Quantity Surveyor"], needs_visa_sponsorship=True)
    blocked = Job("x", "AECOM", "Graduate Quantity Surveyor", "London", "https://e/1",
                  description="You must have permanent right to work in the UK as we are unable to sponsor.")
    ok = Job("x", "D&A", "Junior Quantity Surveyor", "Dubai", "https://e/2", description="Visa provided.")
    assert relevance(blocked, prefs) == "no visa sponsorship"
    assert relevance(ok, prefs) is None


def test_schedule_commands():
    assert schedule.run_command()[-2:] == ["jobagent.cli", "run"]
    assert "*/30 * * * *" in schedule.cron_line(30) and schedule.CRON_MARK in schedule.cron_line(30)
    assert "<integer>1800</integer>" in schedule.launchd_plist(30)
    cmd = schedule.windows_command(30)
    assert cmd[:3] == ["schtasks", "/Create", "/F"] and "JobSearchAgent" in cmd

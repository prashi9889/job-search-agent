# Job Search Agent

A personal, local-first assistant for finding jobs, tailoring applications
and tracking them. The design is in [docs/DPR.md](docs/DPR.md) and the
decisions made so far are in [docs/decisions.md](docs/decisions.md).

**Status:** Phase 1 (setup and privacy) is in review. Gmail monitoring with
automatic interview scheduling is built and waits for you to sign in to
Google. No profile data is stored yet.

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
jobagent init          # creates ~/.jobagent (override with JOBAGENT_HOME)
jobagent serve         # dashboard at http://127.0.0.1:8765
pytest
```

## Privacy controls

```bash
jobagent privacy                        # show current settings
jobagent privacy --external-opt-in on   # allow public job-listing text to reach the external model
jobagent privacy --external-opt-in off
```

Profile, email, draft and tracker data are always processed locally,
whatever these settings say.

## Connecting Google (Gmail + Calendar)

1. In [Google Cloud Console](https://console.cloud.google.com/), create a
   project, enable the **Gmail API** and **Google Calendar API**, set up the
   OAuth consent screen (External, add yourself as a test user), and create an
   **OAuth client ID** of type **Desktop app**.
2. Download its JSON and save it as `~/.jobagent/google_client_secret.json`.
3. Run `jobagent connect google` and approve in the browser window. The
   agent asks for read-only Gmail and Calendar event access.

Then:

```bash
jobagent sync-email               # check the last 3 days once
jobagent sync-email --watch 15    # keep checking every 15 minutes
```

Interview and assessment emails that give a date and time become calendar
events automatically. Anything uncertain is listed in the dashboard's audit
history for you to check. `jobagent privacy --auto-calendar off` stops
automatic events; `jobagent connect google --disconnect` removes access.

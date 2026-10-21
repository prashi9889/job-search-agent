# Job Search Agent

A personal, local-first assistant for finding jobs, tailoring applications
and tracking them. The design is in [docs/DPR.md](docs/DPR.md) and the
decisions made so far are in [docs/decisions.md](docs/decisions.md).

**Status:** Phase 1 (setup and privacy) is in review. Gmail monitoring with
automatic interview scheduling is built and waits for you to sign in to
Google. Profile import is ready; the profile itself is never committed.

## Install (one time)

You need Python 3.11+ ([python.org/downloads](https://www.python.org/downloads/); on
Windows tick "Add python.exe to PATH"). Then download this repository and run:

- **Windows:** right-click the folder → *Open in Terminal*, then
  `powershell -ExecutionPolicy Bypass -File install.ps1 C:\path\to\profile.json`
- **macOS / Linux:** `bash install.sh ~/path/to/profile.json`

This installs the agent, loads your profile and makes it run every 30 minutes
in the background. Stop it with `jobagent schedule remove`.

## Accepting jobs

Open the dashboard (`jobagent serve`, then http://127.0.0.1:8765). Click
**Accept** on a job to approve it and open its application page, **Skip** to
hide it, and **I applied** after you submit. Add a job you found yourself:

```bash
jobagent add-job --title "Junior Quantity Surveyor" --company "D&A Consulting" --location "Dubai" --url "https://..."
```

## Resume humanizer

```bash
jobagent humanize resume.docx   # flags stock AI phrasing, em dashes, long sentences
```

Writing rules are in `.claude/skills/resume-humanizer/SKILL.md`.

## Manual setup

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

## Your profile

```bash
jobagent profile import path/to/profile.json   # saved to ~/.jobagent/profile.json
jobagent profile show
```

Only facts in this file are used for matching and documents. Edit the file and
import it again to correct anything.

## Finding jobs

```bash
jobagent discover            # company portals + job-alert emails from the last 7 days
jobagent discover --no-email # company portals only
```

New relevant jobs appear in the dashboard's **Job shortlist**. For Naukri,
LinkedIn, Indeed and Foundit, create job alerts on each site (Quantity
Surveyor / Billing Engineer / Estimation Engineer, India) sent to the Gmail
account you connect. Company portals are listed in `jobagent/sources.json`.

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

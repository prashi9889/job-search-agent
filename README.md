# Job Search Agent

A personal, local-first assistant for finding jobs, tailoring applications
and tracking them. The design is in [docs/DPR.md](docs/DPR.md) and the
decisions made so far are in [docs/decisions.md](docs/decisions.md).

**Status:** Phase 1 (project setup and privacy choice) is in review. Nothing
connects to Gmail, Microsoft 365 or job sites yet, and no profile data is
stored.

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

# Decisions log

## D1 — Separate repository (2026-10-21)

The agent lives in its own repository, separate from any other project, so
that personal tooling and data never mix with unrelated code.

## D2 — Hybrid AI processing (2026-10-21)

| Data | Processed by |
|---|---|
| Profile facts, emails, resume/cover-letter drafts, tracker records | Local model only (Ollama). There is no setting that sends this data off the machine. |
| Public job-listing text | External model (Claude API) **only** when `ai_mode = hybrid` **and** `external_ai_opt_in = on`. Otherwise local. |

- External opt-in is **off** by default. Change it with
  `jobagent privacy --external-opt-in on|off`; every change is audited.
- Every external call and every blocked attempt is written to the audit log.
- Enforced in `jobagent/privacy.py`. Every model call must go through
  `privacy.require()`.

Open point for Phase 4: matching a listing against the profile combines both
kinds of data, so that comparison step runs locally. The external model may
only summarise or normalise listing text on its own.

## D3 — Python + local web dashboard (2026-10-21)

Python 3.11+, FastAPI dashboard bound to `127.0.0.1`, SQLite for the
append-only audit history. The Excel tracker (Phase 3) will use openpyxl.

## D4 — Local data location (2026-10-21)

All personal data is stored under `$JOBAGENT_HOME` (default `~/.jobagent`),
created with owner-only permissions (`0700`, settings file `0600`). The
repository's `.gitignore` excludes workbooks, databases and `.env` files.

## D5 — Integrations authorized (2026-10-21)

You authorized Gmail, Google Calendar, Microsoft 365 and browser access.

- **Gmail:** read-only scope (`gmail.readonly`). The agent cannot send,
  delete or change mail.
- **Google Calendar:** `calendar.events` scope, used only to add events.
- **Microsoft 365:** authorized; built alongside the Excel tracker (Phase 3).
- **Browser:** authorized for Phase 6 (application assistance). Each
  application is still submitted only after you approve it, as the DPR
  requires. Removing that step would need an explicit change to the DPR.
- The Google sign-in token is stored in the OS keyring, never in files.

## D6 — Interview dates go on the calendar automatically (2026-10-21)

When an interview or assessment email states a date **and** a time, the
agent adds a calendar event without asking (1-day and 1-hour reminders,
with a link back to the email). Safeguards:

- Only emails classified as interview or assessment are used. Rejections,
  offers, newsletters and other mail never create events.
- A date with no time, a past date, or `auto_calendar = off` produces a
  proposed event in the audit history for you to review instead.
- Each email is handled once, and events are tagged so the same email never
  creates the same event twice.
- Every created event is recorded in the audit history with its event id.
- If no time zone is stated, the email's own time zone is used; the event
  description asks you to check the time against the email.
- Turn it off with `jobagent privacy --auto-calendar off`.

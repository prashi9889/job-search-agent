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

## D7 — Job search focus (2026-10-21)

- Target: Quantity Surveying roles anywhere in India (Quantity Surveyor,
  Trainee/Junior QS, Billing Engineer, Estimation Engineer, QS Engineer).
  Available immediately.
- UPVC and aluminium experience stays on the resume, but UPVC/aluminium
  window and door companies are **excluded** from the search until you ask
  otherwise. Exclusions are keyword-based (`preferences.exclude_keywords`),
  so construction jobs that merely mention e.g. aluminium formwork still count.
- The profile lives in `~/.jobagent/profile.json` and is never committed.

## D8 — Job sources (2026-10-21)

**Job sites (Naukri, LinkedIn, Indeed, Foundit):** none offers a public feed,
and their terms forbid scraping. The agent reads the **job-alert emails** they
send, through the existing read-only Gmail access. You create the alerts once
on each site (keywords: Quantity Surveyor, Billing Engineer, Estimation
Engineer; location: India).

**Company career portals (worldwide firms):** queried directly through the
public feeds their careers sites already use:

| Feed | Companies |
|---|---|
| Workday | JLL, Cushman & Wakefield, KBR, Parsons, Surbana Jurong, Knight Frank, Cumming Group, Amentum |
| SmartRecruiters | Turner & Townsend (format checked live) |
| Oracle Recruiting | WSP (format checked live) |
| Link only (no public feed) | AECOM, Jacobs, Arcadis, L&T, RLB, CBRE, Colliers, Tata Projects, Shapoorji Pallonji, Afcons |

Link-only sites are listed on the dashboard as one-click searches. The list is
in `jobagent/sources.json` and can be extended.

**Filtering:** QS-type titles only; UPVC/aluminium companies excluded;
titles with Senior, Principal, Lead, Head, Director or Chief are skipped
(`preferences.exclude_title_words`); location must match the profile
(India, the six Gulf countries and the UK; see D9). The same job found on several sources is stored once.

## D9 — Countries (2026-10-21)

Search covers India, the Gulf (UAE, Qatar, Saudi Arabia, Oman, Kuwait,
Bahrain) and the United Kingdom. Locations are matched by country name, code
and main cities. Listings shown only as "N Locations" are kept for review.

## D10 — All countries; Gulf and UK job sites (2026-10-21)

Location filter removed (`preferences.locations = ["Anywhere"]`): jobs in any
country are kept. NaukriGulf, Bayt, GulfTalent, Reed and Totaljobs alert
emails are read the same way as the Indian job sites. This supersedes D9.

## D11 — Automatic operation, visa filter, humanizer (2026-10-21)

- **Automatic runs:** `install.ps1` (Windows) / `install.sh` (macOS, Linux)
  set up the agent and register `jobagent run` with the OS scheduler (Task
  Scheduler, launchd or cron) every 30 minutes. Each run finds new jobs and,
  once Google is connected, updates the calendar from email.
- **Visa:** the candidate holds Indian citizenship only and is open to any
  country. `needs_visa_sponsorship = true` skips listings whose text says
  they cannot sponsor or require existing right to work. Listings without
  description text are kept.
- **Humanizer:** `.claude/skills/resume-humanizer/SKILL.md` sets the writing
  rules for every resume and cover letter; `jobagent humanize FILE` flags stock
  AI phrasing, em dashes, long sentences and repeated openings. It cannot
  guarantee a score on any particular AI detector.
- **Applications** are still submitted only after explicit approval (DPR §3).

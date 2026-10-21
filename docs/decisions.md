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

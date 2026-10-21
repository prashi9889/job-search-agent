"""Local dashboard. Served on 127.0.0.1 only."""

from __future__ import annotations

from html import escape

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from . import __version__
from .audit import AuditLog
from .config import data_dir, ensure_data_dir, load_settings
from .privacy import DataClass, route

# Mirrors the phased plan in docs/DPR.md. Updated as phases are approved.
PHASES = [
    ("1. Project setup and privacy choice", "In review"),
    ("2. Profile and preferences", "Not started"),
    ("3. Tracker", "Not started"),
    ("4. Job discovery and matching", "Not started"),
    ("5. Tailored documents", "Not started"),
    ("6. Application assistance", "Not started"),
    ("7. Gmail monitoring", "Not authorized"),
    ("8. Ongoing operation", "Not started"),
]


def create_app(audit: AuditLog | None = None) -> FastAPI:
    ensure_data_dir()
    audit = audit or AuditLog(data_dir() / "audit.db")
    app = FastAPI(title="Job Search Agent", version=__version__)

    def status() -> dict:
        settings = load_settings()
        return {
            "version": __version__,
            "data_dir": str(data_dir()),
            "settings": settings.to_json(),
            "routing": {dc.value: route(dc, settings).value for dc in DataClass},
            "phases": [{"phase": p, "status": s} for p, s in PHASES],
            "integrations": {"gmail": "not connected", "microsoft365": "not connected", "job_sources": "none approved"},
        }

    @app.get("/api/status")
    def api_status() -> dict:
        return status()

    @app.get("/api/audit")
    def api_audit(limit: int = 50) -> list[dict]:
        return audit.recent(limit)

    @app.get("/", response_class=HTMLResponse)
    def dashboard() -> str:
        s = status()
        routing = "".join(
            f"<tr><td>{escape(k)}</td><td>{escape(v)}</td></tr>" for k, v in s["routing"].items()
        )
        phases = "".join(
            f"<tr><td>{escape(p['phase'])}</td><td>{escape(p['status'])}</td></tr>" for p in s["phases"]
        )
        integrations = "".join(
            f"<tr><td>{escape(k)}</td><td>{escape(v)}</td></tr>" for k, v in s["integrations"].items()
        )
        events = "".join(
            f"<tr><td>{escape(e['ts'])}</td><td>{escape(e['action'])}</td><td>{escape(e['subject'])}</td></tr>"
            for e in audit.recent(20)
        ) or "<tr><td colspan=3>No events yet</td></tr>"
        cfg = s["settings"]
        return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Job Search Agent</title>
<style>
body {{ font: 15px/1.5 system-ui, sans-serif; max-width: 860px; margin: 2rem auto; padding: 0 1rem; color: #1d1d1f; background: #fafafa; }}
table {{ border-collapse: collapse; width: 100%; margin-bottom: 1.5rem; background: #fff; }}
td, th {{ border: 1px solid #ddd; padding: .4rem .6rem; text-align: left; }}
.note {{ background: #fff8e1; border: 1px solid #f0d58c; padding: .6rem .8rem; }}
</style></head><body>
<h1>Job Search Agent <small>v{escape(s['version'])}</small></h1>
<p class="note">AI mode: <b>{escape(cfg['ai_mode'])}</b> &middot; external AI opt-in:
<b>{'on' if cfg['external_ai_opt_in'] else 'off'}</b> &middot; data: <code>{escape(s['data_dir'])}</code></p>
<h2>Where each kind of data is processed</h2><table>{routing}</table>
<h2>Phases</h2><table>{phases}</table>
<h2>Integrations</h2><table>{integrations}</table>
<h2>Recent audit history</h2><table><tr><th>Time (UTC)</th><th>Action</th><th>Subject</th></tr>{events}</table>
</body></html>"""

    return app

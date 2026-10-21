"""Local dashboard. Served on 127.0.0.1 only."""

from __future__ import annotations

from html import escape

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from . import __version__, google
from .audit import AuditLog
from .config import data_dir, ensure_data_dir, load_settings
from .discovery import link_sources, load_sources
from .jobs import DECISIONS, DuplicateApplication, JobStore
from .privacy import DataClass, route

# Mirrors the phased plan in docs/DPR.md. Updated as phases are approved.
PHASES = [
    ("1. Project setup and privacy choice", "In review"),
    ("2. Profile and preferences", "Built, awaiting profile import"),
    ("3. Tracker", "Not started"),
    ("4. Job discovery and matching", "Discovery built; matching next"),
    ("5. Tailored documents", "Not started"),
    ("6. Application assistance", "Accept / Skip queue on this dashboard"),
    ("7. Gmail monitoring and calendar", "Built, awaiting Google sign-in"),
    ("8. Ongoing operation", "Not started"),
]


class Decision(BaseModel):
    decision: str
    resume_version: str | None = None


def create_app(audit: AuditLog | None = None) -> FastAPI:
    ensure_data_dir()
    audit = audit or AuditLog(data_dir() / "audit.db")
    app = FastAPI(title="Job Search Agent", version=__version__)
    store = JobStore(data_dir() / "jobs.db")

    def status() -> dict:
        settings = load_settings()
        return {
            "version": __version__,
            "data_dir": str(data_dir()),
            "settings": settings.to_json(),
            "routing": {dc.value: route(dc, settings).value for dc in DataClass},
            "phases": [{"phase": p, "status": s} for p, s in PHASES],
            "integrations": {
                "gmail": "connected (read-only)" if google.is_connected() else "not connected",
                "google_calendar": (
                    ("connected, auto-add " + ("on" if settings.auto_calendar else "off"))
                    if google.is_connected() else "not connected"
                ),
                "microsoft365": "authorized, not built yet",
                "job_sources": "Naukri, LinkedIn, Indeed, Foundit (via alert emails) + company portals",
            },
        }

    @app.get("/api/status")
    def api_status() -> dict:
        return status()

    @app.get("/api/jobs")
    def api_jobs(limit: int = 100) -> list[dict]:
        return store.shortlist(limit)

    @app.post("/api/jobs/{job_id}/decision")
    def api_decide(job_id: int, body: Decision, x_jobagent: str | None = Header(default=None)) -> dict:
        # Browsers cannot add this header to a cross-site request without a CORS
        # preflight, which this server never allows, so other sites cannot click for you.
        if x_jobagent != "1":
            raise HTTPException(403, "missing X-Jobagent header")
        if body.decision not in DECISIONS:
            raise HTTPException(400, "unknown decision")
        try:
            job = store.decide(job_id, body.decision, body.resume_version)
        except KeyError:
            raise HTTPException(404, "no such job")
        except DuplicateApplication as exc:
            audit.record("application.duplicate_blocked", f"job:{job_id}", {"reason": str(exc)}, actor="user")
            raise HTTPException(409, str(exc))
        audit.record(f"application.{body.decision}", f"job:{job_id}",
                     {"company": job["company"], "title": job["title"], "stage": job["stage"]}, actor="user")
        return job

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
        def buttons(j: dict) -> str:
            if j["stage"] == "approved":
                return (f'<span class="ok">Accepted</span> '
                        f'<button data-id="{j["id"]}" data-d="applied">I applied</button> '
                        f'<button data-id="{j["id"]}" data-d="undo" class="ghost">Undo</button>')
            return (f'<button data-id="{j["id"]}" data-d="accept" data-url="{escape(j["url"])}" class="go">Accept</button> '
                    f'<button data-id="{j["id"]}" data-d="skip" class="ghost">Skip</button>')

        jobs = "".join(
            f"<tr><td><a href=\"{escape(j['url'])}\" rel=\"noopener noreferrer\" target=\"_blank\">{escape(j['title'])}</a></td>"
            f"<td>{escape(j['company'])}</td><td>{escape(j['location'])}</td><td>{escape(j['source'])}</td>"
            f"<td class=\"act\">{buttons(j)}</td></tr>"
            for j in store.shortlist(50)
        ) or "<tr><td colspan=5>No jobs yet. Run <code>jobagent discover</code>.</td></tr>"
        applied = "".join(
            f"<tr><td><a href=\"{escape(j['url'])}\" rel=\"noopener noreferrer\" target=\"_blank\">{escape(j['title'])}</a></td>"
            f"<td>{escape(j['company'])}</td><td>{escape((j['applied_at'] or '')[:10])}</td></tr>"
            for j in store.shortlist(50, stages=("applied",))
        ) or "<tr><td colspan=3>None yet</td></tr>"
        links = " &middot; ".join(
            f"<a href=\"{escape(l['url'])}\" target=\"_blank\" rel=\"noopener noreferrer\">{escape(l['name'])}</a>"
            for l in link_sources(load_sources())
        )
        cfg = s["settings"]
        return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Job Search Agent</title>
<style>
body {{ font: 15px/1.5 system-ui, sans-serif; max-width: 860px; margin: 2rem auto; padding: 0 1rem; color: #1d1d1f; background: #fafafa; }}
table {{ border-collapse: collapse; width: 100%; margin-bottom: 1.5rem; background: #fff; }}
td, th {{ border: 1px solid #ddd; padding: .4rem .6rem; text-align: left; }}
.note {{ background: #fff8e1; border: 1px solid #f0d58c; padding: .6rem .8rem; }}
button {{ font: inherit; padding: .25rem .7rem; border-radius: 6px; border: 1px solid #888; background: #fff; cursor: pointer; }}
button.go {{ background: #1f7a3a; border-color: #1f7a3a; color: #fff; }}
button.ghost {{ color: #555; }}
.act {{ white-space: nowrap; }} .ok {{ color: #1f7a3a; font-weight: 600; }}
.table-wrap {{ overflow-x: auto; }}
</style></head><body>
<h1>Job Search Agent <small>v{escape(s['version'])}</small></h1>
<p class="note">AI mode: <b>{escape(cfg['ai_mode'])}</b> &middot; external AI opt-in:
<b>{'on' if cfg['external_ai_opt_in'] else 'off'}</b> &middot; data: <code>{escape(s['data_dir'])}</code></p>
<h2>Job shortlist</h2>
<p>Nothing is sent to an employer until you click <b>Accept</b>. Accept opens the application page; click
<b>I applied</b> once you have submitted it.</p>
<div class="table-wrap"><table><tr><th>Role</th><th>Company</th><th>Location</th><th>Source</th><th></th></tr>{jobs}</table></div>
<h2>Applied</h2><table><tr><th>Role</th><th>Company</th><th>Date</th></tr>{applied}</table>
<p>Also check these career sites (no automatic feed): {links}</p>
<h2>Where each kind of data is processed</h2><table>{routing}</table>
<h2>Phases</h2><table>{phases}</table>
<h2>Integrations</h2><table>{integrations}</table>
<h2>Recent audit history</h2><table><tr><th>Time (UTC)</th><th>Action</th><th>Subject</th></tr>{events}</table>
<script>
document.addEventListener("click", async (e) => {{
  const b = e.target.closest("button[data-id]");
  if (!b) return;
  b.disabled = true;
  const r = await fetch(`/api/jobs/${{b.dataset.id}}/decision`, {{
    method: "POST",
    headers: {{"Content-Type": "application/json", "X-Jobagent": "1"}},
    body: JSON.stringify({{decision: b.dataset.d}}),
  }});
  if (!r.ok) {{ alert((await r.json()).detail || "Could not save"); b.disabled = false; return; }}
  if (b.dataset.d === "accept" && b.dataset.url) window.open(b.dataset.url, "_blank", "noopener");
  location.reload();
}});
</script>
</body></html>"""

    return app

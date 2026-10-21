"""Command line: init, serve, privacy, profile, connect, sync-email."""

from __future__ import annotations

import argparse
import json
import time

from .audit import AuditLog
from .config import data_dir, ensure_data_dir, load_settings, save_settings, settings_path


def _audit() -> AuditLog:
    ensure_data_dir()
    return AuditLog(data_dir() / "audit.db")


def cmd_init(_args) -> None:
    ensure_data_dir()
    created = not settings_path().exists()
    if created:
        save_settings(load_settings())
    _audit().record("project.init", str(data_dir()), {"settings_created": created}, actor="user")
    print(f"Data directory: {data_dir()}")
    print(json.dumps(load_settings().to_json(), indent=2))


def cmd_privacy(args) -> None:
    settings = load_settings()
    if args.external_opt_in is not None:
        before = settings.external_ai_opt_in
        settings.external_ai_opt_in = args.external_opt_in == "on"
        save_settings(settings)
        _audit().record(
            "privacy.opt_in_changed",
            "external_ai",
            {"from": before, "to": settings.external_ai_opt_in},
            actor="user",
        )
    if args.auto_calendar is not None:
        before = settings.auto_calendar
        settings.auto_calendar = args.auto_calendar == "on"
        save_settings(settings)
        _audit().record(
            "calendar.auto_changed", "calendar", {"from": before, "to": settings.auto_calendar}, actor="user"
        )
    print(json.dumps(settings.to_json(), indent=2))


def cmd_profile(args) -> None:
    from .profile import load_profile, profile_path, save_profile, validate

    if args.action == "import":
        with open(args.file, encoding="utf-8") as f:
            profile = json.load(f)
        problems = validate(profile)
        if problems:
            raise SystemExit("Profile not saved: " + "; ".join(problems))
        save_profile(profile)
        _audit().record("profile.imported", str(profile_path()), {"sections": sorted(profile)}, actor="user")
        print(f"Profile saved to {profile_path()}")
        return
    profile = load_profile()
    if profile is None:
        raise SystemExit("No profile yet. Run `jobagent profile import FILE`.")
    print(json.dumps(profile, indent=2, ensure_ascii=False))


def cmd_connect(args) -> None:
    from . import google

    if args.disconnect:
        google.disconnect()
        _audit().record("integration.disconnected", "google", actor="user")
        print("Google disconnected.")
        return
    if not google.client_secret_path().exists():
        raise SystemExit(
            f"Put your Google OAuth client file at {google.client_secret_path()} first "
            "(see README, 'Connecting Google')."
        )
    google.credentials(interactive=True)
    _audit().record("integration.connected", "google", {"scopes": google.SCOPES}, actor="user")
    print("Google connected: Gmail (read-only) and Calendar events.")


def cmd_sync_email(args) -> None:
    from . import google
    from .sync import sync_email

    audit = _audit()
    while True:
        settings = load_settings()
        creds = google.credentials()
        messages = google.GmailReader(creds).recent(args.days)
        calendar = google.GoogleCalendar(creds, settings.calendar_id)
        results = sync_email(messages, calendar, settings, audit)
        audit.record("email.sync", "gmail", {"messages": len(messages), **results})
        print(f"{time.strftime('%H:%M')} checked {len(messages)} emails: {dict(results)}")
        if not args.watch:
            return
        time.sleep(args.watch * 60)


def cmd_serve(args) -> None:
    import uvicorn

    from .app import create_app

    # Bound to loopback so the dashboard is never reachable from the network.
    uvicorn.run(create_app(), host="127.0.0.1", port=args.port)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="jobagent")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="create the local data directory and settings").set_defaults(func=cmd_init)

    p = sub.add_parser("privacy", help="show or change AI processing settings")
    p.add_argument("--external-opt-in", choices=["on", "off"],
                   help="allow public job-listing text to be sent to the external model")
    p.add_argument("--auto-calendar", choices=["on", "off"],
                   help="add interview and assessment dates from email to the calendar automatically")
    p.set_defaults(func=cmd_privacy)

    p = sub.add_parser("profile", help="show or import your verified profile")
    p.add_argument("action", choices=["show", "import"])
    p.add_argument("file", nargs="?", help="profile JSON to import")
    p.set_defaults(func=cmd_profile)

    p = sub.add_parser("connect", help="sign in to Google (Gmail read-only + Calendar)")
    p.add_argument("service", choices=["google"])
    p.add_argument("--disconnect", action="store_true")
    p.set_defaults(func=cmd_connect)

    p = sub.add_parser("sync-email", help="read recent job emails and update the calendar")
    p.add_argument("--days", type=int, default=3, help="how far back to look")
    p.add_argument("--watch", type=int, metavar="MINUTES", help="keep running, checking every MINUTES")
    p.set_defaults(func=cmd_sync_email)

    p = sub.add_parser("serve", help="run the local dashboard")
    p.add_argument("--port", type=int, default=8765)
    p.set_defaults(func=cmd_serve)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()

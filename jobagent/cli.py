"""Command line: `jobagent init`, `jobagent serve`, `jobagent privacy`."""

from __future__ import annotations

import argparse
import json

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
    print(json.dumps(settings.to_json(), indent=2))


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
    p.set_defaults(func=cmd_privacy)

    p = sub.add_parser("serve", help="run the local dashboard")
    p.add_argument("--port", type=int, default=8765)
    p.set_defaults(func=cmd_serve)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()

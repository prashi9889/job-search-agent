"""Local data directory and settings.

All personal data lives under one directory on the user's machine
($JOBAGENT_HOME, default ~/.jobagent), created with owner-only permissions.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path


class AIMode(str, Enum):
    # Everything is processed by a model on this computer.
    LOCAL = "local"
    # Profile, email and draft data stay local; public job-listing text may be
    # sent to an external model, but only after an explicit opt-in.
    HYBRID = "hybrid"


@dataclass
class Settings:
    ai_mode: AIMode = AIMode.HYBRID
    # Off until the user turns it on. Even in hybrid mode nothing leaves the
    # machine while this is False.
    external_ai_opt_in: bool = False
    local_model: str = "llama3.1:8b"
    local_model_url: str = "http://127.0.0.1:11434"
    external_model: str = "claude-sonnet-5-5"
    # Add interview and assessment dates found in email straight to the
    # calendar. Dates without an explicit time are proposed for review instead.
    auto_calendar: bool = True
    calendar_id: str = "primary"
    event_minutes: int = 60

    def to_json(self) -> dict:
        data = asdict(self)
        data["ai_mode"] = self.ai_mode.value
        return data

    @classmethod
    def from_json(cls, data: dict) -> "Settings":
        known = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        if "ai_mode" in known:
            known["ai_mode"] = AIMode(known["ai_mode"])
        return cls(**known)


def data_dir() -> Path:
    return Path(os.environ.get("JOBAGENT_HOME", Path.home() / ".jobagent"))


def settings_path() -> Path:
    return data_dir() / "settings.json"


def ensure_data_dir() -> Path:
    path = data_dir()
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(path, 0o700)
    return path


def load_settings() -> Settings:
    path = settings_path()
    if not path.exists():
        return Settings()
    return Settings.from_json(json.loads(path.read_text()))


def save_settings(settings: Settings) -> None:
    ensure_data_dir()
    path = settings_path()
    path.write_text(json.dumps(settings.to_json(), indent=2) + "\n")
    os.chmod(path, 0o600)

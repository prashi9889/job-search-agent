"""Verified profile and job-search preferences.

Stored as `profile.json` in the local data directory, never in the repository.
Only facts in this file may be used in matching and generated documents.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from .config import data_dir, ensure_data_dir

REQUIRED_SECTIONS = ("contact", "education", "experience", "skills", "preferences")


def profile_path() -> Path:
    return data_dir() / "profile.json"


def validate(profile: dict) -> list[str]:
    problems = [f"missing section: {s}" for s in REQUIRED_SECTIONS if s not in profile]
    prefs = profile.get("preferences", {})
    if not prefs.get("target_roles"):
        problems.append("preferences.target_roles is empty")
    return problems


def load_profile() -> dict | None:
    path = profile_path()
    return json.loads(path.read_text()) if path.exists() else None


def save_profile(profile: dict) -> None:
    problems = validate(profile)
    if problems:
        raise ValueError("; ".join(problems))
    ensure_data_dir()
    path = profile_path()
    path.write_text(json.dumps(profile, indent=2, ensure_ascii=False) + "\n")
    os.chmod(path, 0o600)


@dataclass
class SearchPreferences:
    target_roles: list[str]
    locations: list[str] = field(default_factory=list)
    # Listings mentioning any of these (company, title or description) are skipped.
    exclude_keywords: list[str] = field(default_factory=list)

    @classmethod
    def from_profile(cls, profile: dict) -> "SearchPreferences":
        prefs = profile["preferences"]
        return cls(
            target_roles=prefs["target_roles"],
            locations=prefs.get("locations", []),
            exclude_keywords=prefs.get("exclude_keywords", []),
        )

    def excluded_by(self, *texts: str) -> str | None:
        """The first exclude keyword found in the listing text, if any."""
        blob = " ".join(texts)
        for kw in self.exclude_keywords:
            if re.search(rf"\b{re.escape(kw)}\b", blob, re.I):
                return kw
        return None

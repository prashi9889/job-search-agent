"""Decides which model may process a piece of data.

Every model call must go through `route()` first. The rules implement the
hybrid decision recorded in docs/decisions.md:

- Profile facts, emails, drafts and tracker records are always processed
  locally. There is no setting that sends them to an external service.
- Public job-listing text may go to the external model only in hybrid mode
  and only after the user has opted in. Otherwise it is processed locally.
"""

from __future__ import annotations

from enum import Enum

from .audit import AuditLog
from .config import AIMode, Settings


class DataClass(str, Enum):
    JOB_LISTING = "job_listing"
    PROFILE = "profile"
    EMAIL = "email"
    DRAFT = "draft"
    TRACKER = "tracker"


class Processor(str, Enum):
    LOCAL = "local"
    EXTERNAL = "external"


# Data that contains personal information and must never leave the machine.
PERSONAL = frozenset({DataClass.PROFILE, DataClass.EMAIL, DataClass.DRAFT, DataClass.TRACKER})


class PrivacyViolation(Exception):
    pass


def route(data_class: DataClass, settings: Settings) -> Processor:
    if data_class in PERSONAL:
        return Processor.LOCAL
    if settings.ai_mode is AIMode.HYBRID and settings.external_ai_opt_in:
        return Processor.EXTERNAL
    return Processor.LOCAL


def require(
    data_class: DataClass,
    processor: Processor,
    settings: Settings,
    audit: AuditLog | None = None,
    purpose: str = "",
) -> None:
    """Raise unless `processor` is allowed for `data_class`; audit external use."""
    allowed = route(data_class, settings)
    if processor is Processor.EXTERNAL and allowed is not Processor.EXTERNAL:
        if audit:
            audit.record("privacy.blocked", data_class.value, {"purpose": purpose})
        raise PrivacyViolation(
            f"{data_class.value} data may not be sent to an external model"
        )
    if processor is Processor.EXTERNAL and audit:
        audit.record(
            "privacy.external_call",
            data_class.value,
            {"purpose": purpose, "model": settings.external_model},
        )

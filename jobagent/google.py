"""Google sign-in, read-only Gmail and Calendar event access.

The OAuth token is kept in the operating system's keyring, never on disk in
the data directory or the repository.
"""

from __future__ import annotations

import base64
import json
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

from .config import data_dir
from .emails import EmailMessage

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar.events",
]
KEYRING_SERVICE = "jobagent"
KEYRING_USER = "google-token"

# Messages likely to be about a job application.
JOB_QUERY = (
    "(interview OR assessment OR application OR applied OR recruiter OR offer OR "
    "\"phone screen\" OR \"next steps\" OR hiring OR candidate) -category:promotions"
)


def client_secret_path():
    return data_dir() / "google_client_secret.json"


def is_connected() -> bool:
    try:
        import keyring
        return keyring.get_password(KEYRING_SERVICE, KEYRING_USER) is not None
    except Exception:
        return False


def credentials(interactive: bool = False):
    import keyring
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    stored = keyring.get_password(KEYRING_SERVICE, KEYRING_USER)
    creds = Credentials.from_authorized_user_info(json.loads(stored), SCOPES) if stored else None
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    if not creds or not creds.valid:
        if not interactive:
            raise RuntimeError("Google is not connected. Run `jobagent connect google`.")
        from google_auth_oauthlib.flow import InstalledAppFlow

        flow = InstalledAppFlow.from_client_secrets_file(str(client_secret_path()), SCOPES)
        creds = flow.run_local_server(host="127.0.0.1", port=0)
    keyring.set_password(KEYRING_SERVICE, KEYRING_USER, creds.to_json())
    return creds


def disconnect() -> None:
    import keyring
    keyring.delete_password(KEYRING_SERVICE, KEYRING_USER)


def _body_text(payload: dict) -> str:
    if payload.get("mimeType") == "text/plain" and payload.get("body", {}).get("data"):
        return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", "replace")
    return "\n".join(filter(None, (_body_text(p) for p in payload.get("parts", []))))


class GmailReader:
    def __init__(self, creds):
        from googleapiclient.discovery import build
        self._svc = build("gmail", "v1", credentials=creds, cache_discovery=False)

    def recent(self, days: int, limit: int = 200) -> list[EmailMessage]:
        resp = self._svc.users().messages().list(
            userId="me", q=f"newer_than:{days}d {JOB_QUERY}", maxResults=limit
        ).execute()
        return [self._get(m["id"]) for m in resp.get("messages", [])]

    def _get(self, message_id: str) -> EmailMessage:
        m = self._svc.users().messages().get(userId="me", id=message_id, format="full").execute()
        headers = {h["name"].lower(): h["value"] for h in m["payload"].get("headers", [])}
        try:
            received = parsedate_to_datetime(headers["date"])
        except (KeyError, TypeError, ValueError):
            received = datetime.fromtimestamp(int(m["internalDate"]) / 1000, timezone.utc)
        if received.tzinfo is None:
            received = received.replace(tzinfo=timezone.utc)
        return EmailMessage(
            id=m["id"],
            thread_id=m.get("threadId", ""),
            sender=headers.get("from", ""),
            subject=headers.get("subject", ""),
            body=_body_text(m["payload"]) or m.get("snippet", ""),
            received_at=received,
        )


class GoogleCalendar:
    def __init__(self, creds, calendar_id: str = "primary"):
        from googleapiclient.discovery import build
        self._svc = build("calendar", "v3", credentials=creds, cache_discovery=False)
        self._cal = calendar_id

    def find_by_key(self, key: str) -> dict | None:
        items = self._svc.events().list(
            calendarId=self._cal, privateExtendedProperty=f"jobagent_key={key}", maxResults=1
        ).execute().get("items", [])
        return items[0] if items else None

    def insert(self, event: dict) -> str:
        return self._svc.events().insert(calendarId=self._cal, body=event).execute()["id"]

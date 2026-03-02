from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Protocol

from sqlalchemy.orm import Session

from app.config import settings
from app.models import CalendarEvent


class CalendarProvider(Protocol):
    name: str

    def load_events(self) -> list[dict]:
        ...


class MockGoogleCalendarProvider:
    name = "google"

    def __init__(self, path: str) -> None:
        self.path = Path(path)

    def load_events(self) -> list[dict]:
        if not self.path.exists():
            self.path.write_text("[]", encoding="utf-8")
            return []
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []


def get_default_calendar_provider() -> CalendarProvider:
    return MockGoogleCalendarProvider(settings.google_calendar_mock_path)


def sync_calendar(db: Session, provider: CalendarProvider) -> dict[str, int | str]:
    events = provider.load_events()
    upserted = 0

    for item in events:
        provider_event_id = str(item.get("id"))
        if not provider_event_id:
            continue
        start_at = datetime.fromisoformat(item["start_at"])
        end_at = datetime.fromisoformat(item["end_at"])

        existing = (
            db.query(CalendarEvent)
            .filter(CalendarEvent.provider == provider.name, CalendarEvent.provider_event_id == provider_event_id)
            .first()
        )
        if existing:
            existing.title = item.get("title", existing.title)
            existing.start_at = start_at
            existing.end_at = end_at
            existing.location = item.get("location")
            existing.attendees_json = item.get("attendees", [])
            existing.synced_at = datetime.utcnow()
        else:
            db.add(
                CalendarEvent(
                    provider=provider.name,
                    provider_event_id=provider_event_id,
                    title=item.get("title", "Untitled Event"),
                    start_at=start_at,
                    end_at=end_at,
                    location=item.get("location"),
                    attendees_json=item.get("attendees", []),
                    synced_at=datetime.utcnow(),
                )
            )
        upserted += 1

    db.commit()
    return {"upserted": upserted, "source": f"{provider.name}:mock"}


def sync_google_calendar(db: Session) -> dict[str, int | str]:
    return sync_calendar(db, get_default_calendar_provider())

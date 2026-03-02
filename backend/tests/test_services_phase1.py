from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace

from sqlalchemy.orm import Session

from app.config import settings
from app.models import Contact, Conversation, Message, Task
from app.services.ai_pipeline import apply_message_insights
from app.services.telegram_connector import sync_telegram_updates


def test_apply_message_insights_sets_work_category_and_source_platform(db: Session) -> None:
    now = datetime.utcnow()
    contact = Contact(
        platform="telegram",
        platform_user_id="u-3",
        display_name="Carol",
        tags_json={"manual": [], "ai": [], "pending": []},
        first_seen_at=now,
        last_seen_at=now,
    )
    db.add(contact)
    db.flush()

    conversation = Conversation(platform="telegram", platform_chat_id="chat-3", contact_id=contact.id, title="Carol")
    db.add(conversation)
    db.flush()

    message = Message(
        conversation_id=conversation.id,
        platform_message_id="m-2",
        sender_role="contact",
        content="Please follow up this project task tomorrow",
        sent_at=now,
        raw_payload_json={},
    )
    db.add(message)
    db.commit()
    db.refresh(message)

    apply_message_insights(db, message)
    db.commit()

    created = db.query(Task).filter(Task.source_message_id == message.id).all()
    assert len(created) == 1
    assert created[0].source_platform == "telegram"
    assert created[0].work_category == "general_work"
    assert created[0].due_at is None or created[0].due_at <= now + timedelta(days=2)


def test_sync_telegram_updates_idempotent(monkeypatch, db: Session) -> None:
    class FakeMessage:
        def __init__(self) -> None:
            self.text = "Need to follow up this project task"
            self.message_id = 111
            self.date = datetime.utcnow()

        def to_dict(self):
            return {
                "message_id": self.message_id,
                "text": self.text,
                "from": {"id": 9001, "username": "alice", "first_name": "Alice"},
                "chat": {"id": 7001, "title": "Alice Chat"},
            }

    class FakeUpdate:
        def __init__(self) -> None:
            self.update_id = 500
            self.effective_message = FakeMessage()

    class FakeBot:
        def __init__(self, token: str) -> None:
            self.token = token

        def get_updates(self, **kwargs):
            return [FakeUpdate()]

    monkeypatch.setattr(settings, "telegram_bot_token", "fake-token")
    import telegram

    monkeypatch.setattr(telegram, "Bot", FakeBot)

    first = sync_telegram_updates(db)
    second = sync_telegram_updates(db)

    assert first["stored_messages"] == 1
    assert second["stored_messages"] == 0
    assert second["duplicates_skipped"] == 1

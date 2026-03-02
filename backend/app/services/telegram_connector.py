from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.config import settings
from app.models import AppState, Contact, Conversation, Message
from app.services.ai_pipeline import apply_message_insights
from app.services.platform_metadata import parse_platform_metadata


def _get_state(db: Session, key: str, default: str = "0") -> str:
    state = db.query(AppState).filter(AppState.key == key).first()
    if not state:
        state = AppState(key=key, value=default)
        db.add(state)
        db.flush()
    return state.value


def _set_state(db: Session, key: str, value: str) -> None:
    state = db.query(AppState).filter(AppState.key == key).first()
    if not state:
        state = AppState(key=key, value=value)
        db.add(state)
    else:
        state.value = value


def _upsert_contact_and_conversation(db: Session, msg: dict[str, Any]) -> tuple[Contact, Conversation]:
    from_user = msg.get("from", {})
    chat = msg.get("chat", {})

    platform_user_id = str(from_user.get("id", chat.get("id", "unknown")))
    display_name = (
        from_user.get("username")
        or " ".join(x for x in [from_user.get("first_name"), from_user.get("last_name")] if x)
        or chat.get("title")
        or platform_user_id
    )

    contact = (
        db.query(Contact)
        .filter(Contact.platform == "telegram", Contact.platform_user_id == platform_user_id)
        .first()
    )
    if not contact:
        contact = Contact(
            platform="telegram",
            platform_user_id=platform_user_id,
            display_name=display_name,
            tags_json={"manual": [], "ai": [], "pending": []},
            first_seen_at=datetime.utcnow(),
            last_seen_at=datetime.utcnow(),
        )
        db.add(contact)
        db.flush()
    else:
        contact.display_name = display_name
        contact.last_seen_at = datetime.utcnow()

    platform_chat_id = str(chat.get("id", platform_user_id))
    conv = (
        db.query(Conversation)
        .filter(Conversation.platform == "telegram", Conversation.platform_chat_id == platform_chat_id)
        .first()
    )
    if not conv:
        conv = Conversation(
            platform="telegram",
            platform_chat_id=platform_chat_id,
            contact_id=contact.id,
            title=chat.get("title") or display_name,
        )
        db.add(conv)
        db.flush()

    return contact, conv


def sync_telegram_updates(db: Session) -> dict[str, int]:
    if not settings.telegram_bot_token:
        return {"fetched_updates": 0, "stored_messages": 0, "processed_with_ai": 0, "skipped": 1}

    from telegram import Bot

    offset = int(_get_state(db, "telegram_last_update_id", "0"))
    bot = Bot(token=settings.telegram_bot_token)
    updates = bot.get_updates(offset=offset + 1, timeout=1, allowed_updates=["message"])

    stored_messages = 0
    processed_with_ai = 0
    duplicates_skipped = 0
    non_text_skipped = 0
    parse_errors = 0
    max_update_id = offset

    for update in updates:
        max_update_id = max(max_update_id, update.update_id)
        message = update.effective_message
        if not message or not message.text:
            non_text_skipped += 1
            continue

        payload = message.to_dict()
        metadata = parse_platform_metadata("telegram", payload)
        if not metadata.get("platform_user_id") or not metadata.get("platform_chat_id"):
            parse_errors += 1
            continue

        _, conversation = _upsert_contact_and_conversation(db, payload)

        existing = (
            db.query(Message)
            .filter(
                Message.conversation_id == conversation.id,
                Message.platform_message_id == str(message.message_id),
            )
            .first()
        )
        if existing:
            duplicates_skipped += 1
            continue

        content = message.text if settings.persist_raw_message_content else (message.text[:5000])
        msg = Message(
            conversation_id=conversation.id,
            platform_message_id=str(message.message_id),
            sender_role="contact",
            content=content,
            sent_at=message.date.replace(tzinfo=None) if message.date else datetime.utcnow(),
            raw_payload_json=payload,
        )
        db.add(msg)
        db.flush()
        stored_messages += 1

        apply_message_insights(db, msg)
        processed_with_ai += 1

    _set_state(db, "telegram_last_update_id", str(max_update_id))
    db.commit()

    return {
        "fetched_updates": len(updates),
        "stored_messages": stored_messages,
        "processed_with_ai": processed_with_ai,
        "duplicates_skipped": duplicates_skipped,
        "non_text_skipped": non_text_skipped,
        "parse_errors": parse_errors,
        "skipped": 0,
    }


def send_telegram_message(text: str) -> bool:
    if not settings.telegram_bot_token or not settings.telegram_notify_chat_id:
        return False
    try:
        from telegram import Bot

        bot = Bot(token=settings.telegram_bot_token)
        bot.send_message(chat_id=settings.telegram_notify_chat_id, text=text)
        return True
    except Exception:
        return False

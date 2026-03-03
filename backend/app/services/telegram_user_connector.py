from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.config import settings
from app.models import AppState, Contact, Conversation, Message
from app.services.ai_pipeline import apply_message_insights


def _get_state(db: Session, key: str, default: str = "") -> str:
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


def _upsert_contact_and_conversation(
    db: Session,
    platform_user_id: str,
    platform_chat_id: str,
    display_name: str,
) -> tuple[Contact, Conversation]:
    contact = (
        db.query(Contact)
        .filter(Contact.platform == "telegram_user", Contact.platform_user_id == platform_user_id)
        .first()
    )
    now = datetime.utcnow()
    if not contact:
        contact = Contact(
            platform="telegram_user",
            platform_user_id=platform_user_id,
            display_name=display_name,
            tags_json={"manual": [], "ai": [], "pending": []},
            first_seen_at=now,
            last_seen_at=now,
        )
        db.add(contact)
        db.flush()
    else:
        contact.display_name = display_name
        contact.last_seen_at = now

    conv = (
        db.query(Conversation)
        .filter(Conversation.platform == "telegram_user", Conversation.platform_chat_id == platform_chat_id)
        .first()
    )
    if not conv:
        conv = Conversation(
            platform="telegram_user",
            platform_chat_id=platform_chat_id,
            contact_id=contact.id,
            title=display_name,
        )
        db.add(conv)
        db.flush()
    else:
        conv.title = display_name

    return contact, conv


async def _async_sync_telegram_user_updates(db: Session) -> dict[str, int]:
    if not (settings.telegram_user_api_id and settings.telegram_user_api_hash and settings.telegram_user_string_session):
        return {
            "dialogs_scanned": 0,
            "messages_scanned": 0,
            "stored_messages": 0,
            "processed_with_ai": 0,
            "duplicates_skipped": 0,
            "outgoing_skipped": 0,
            "non_text_skipped": 0,
            "skipped": 1,
        }

    from telethon import TelegramClient
    from telethon.sessions import StringSession

    last_sync_iso = _get_state(db, "telegram_user_last_sync_at", "")
    if last_sync_iso:
        try:
            last_sync_at = datetime.fromisoformat(last_sync_iso)
        except ValueError:
            last_sync_at = datetime(1970, 1, 1)
    else:
        last_sync_at = datetime(1970, 1, 1)

    dialogs_scanned = 0
    messages_scanned = 0
    stored_messages = 0
    processed_with_ai = 0
    duplicates_skipped = 0
    outgoing_skipped = 0
    non_text_skipped = 0
    latest_seen = last_sync_at

    async with TelegramClient(
        StringSession(settings.telegram_user_string_session),
        settings.telegram_user_api_id,
        settings.telegram_user_api_hash,
    ) as client:
        async for dialog in client.iter_dialogs(limit=settings.telegram_user_dialog_limit):
            dialogs_scanned += 1
            chat_id = str(dialog.id)
            display_name = dialog.name or f"chat:{chat_id}"
            platform_user_id = chat_id
            _, conversation = _upsert_contact_and_conversation(db, platform_user_id, chat_id, display_name)

            async for msg in client.iter_messages(dialog.entity, limit=settings.telegram_user_message_limit):
                messages_scanned += 1
                if not getattr(msg, "message", None):
                    non_text_skipped += 1
                    continue
                if msg.out and not settings.telegram_user_include_outgoing:
                    outgoing_skipped += 1
                    continue

                sent_at = msg.date
                if sent_at and sent_at.tzinfo is not None:
                    sent_at = sent_at.astimezone(timezone.utc).replace(tzinfo=None)
                if not sent_at:
                    sent_at = datetime.utcnow()

                if sent_at <= last_sync_at:
                    continue
                if sent_at > latest_seen:
                    latest_seen = sent_at

                existing = (
                    db.query(Message)
                    .filter(
                        Message.conversation_id == conversation.id,
                        Message.platform_message_id == str(msg.id),
                    )
                    .first()
                )
                if existing:
                    duplicates_skipped += 1
                    continue

                text = msg.message if settings.persist_raw_message_content else msg.message[:5000]
                message = Message(
                    conversation_id=conversation.id,
                    platform_message_id=str(msg.id),
                    sender_role="user" if msg.out else "contact",
                    content=text,
                    sent_at=sent_at,
                    raw_payload_json={
                        "platform": "telegram_user",
                        "chat_id": chat_id,
                        "sender_id": str(msg.sender_id) if msg.sender_id is not None else None,
                        "seed": False,
                    },
                )
                db.add(message)
                db.flush()
                stored_messages += 1

                if not msg.out:
                    apply_message_insights(db, message)
                    processed_with_ai += 1

    _set_state(db, "telegram_user_last_sync_at", latest_seen.isoformat())
    db.commit()

    return {
        "dialogs_scanned": dialogs_scanned,
        "messages_scanned": messages_scanned,
        "stored_messages": stored_messages,
        "processed_with_ai": processed_with_ai,
        "duplicates_skipped": duplicates_skipped,
        "outgoing_skipped": outgoing_skipped,
        "non_text_skipped": non_text_skipped,
        "skipped": 0,
    }


def sync_telegram_user_updates(db: Session) -> dict[str, int]:
    return asyncio.run(_async_sync_telegram_user_updates(db))

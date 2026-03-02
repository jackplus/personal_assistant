from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

from app.config import settings
from app.db import Base, SessionLocal, engine
from app.models import Contact, Conversation, Message, Task, TaskStatus
from app.services.ai_pipeline import apply_message_insights
from app.services.calendar_sync import sync_google_calendar
from app.services.summary_service import generate_daily_summary


def upsert_contact(db, platform: str, platform_user_id: str, display_name: str, tags: dict) -> Contact:
    contact = (
        db.query(Contact)
        .filter(Contact.platform == platform, Contact.platform_user_id == platform_user_id)
        .first()
    )
    now = datetime.utcnow()
    if not contact:
        contact = Contact(
            platform=platform,
            platform_user_id=platform_user_id,
            display_name=display_name,
            tags_json=tags,
            first_seen_at=now,
            last_seen_at=now,
        )
        db.add(contact)
        db.flush()
        return contact

    contact.display_name = display_name
    contact.tags_json = tags
    contact.last_seen_at = now
    db.flush()
    return contact


def upsert_conversation(db, platform: str, platform_chat_id: str, contact_id: int, title: str) -> Conversation:
    conv = (
        db.query(Conversation)
        .filter(Conversation.platform == platform, Conversation.platform_chat_id == platform_chat_id)
        .first()
    )
    if conv:
        conv.title = title
        db.flush()
        return conv

    conv = Conversation(platform=platform, platform_chat_id=platform_chat_id, contact_id=contact_id, title=title)
    db.add(conv)
    db.flush()
    return conv


def upsert_message(db, conversation_id: int, platform_message_id: str, content: str, sent_at: datetime) -> Message:
    msg = (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id, Message.platform_message_id == platform_message_id)
        .first()
    )
    if msg:
        msg.content = content
        msg.sent_at = sent_at
        db.flush()
        return msg

    msg = Message(
        conversation_id=conversation_id,
        platform_message_id=platform_message_id,
        sender_role="contact",
        content=content,
        sent_at=sent_at,
        raw_payload_json={"seed": True},
    )
    db.add(msg)
    db.flush()
    return msg


def upsert_task(
    db,
    title: str,
    due_at: datetime,
    assignee_name: str,
    work_category: str,
    status: TaskStatus = TaskStatus.TODO,
    priority: int = 3,
) -> Task:
    task = db.query(Task).filter(Task.title == title, Task.assignee_name == assignee_name).first()
    if task:
        task.due_at = due_at
        task.work_category = work_category
        task.source_platform = "telegram"
        task.status = status
        task.priority = priority
        db.flush()
        return task

    task = Task(
        title=title,
        description="Seeded demo task",
        due_at=due_at,
        assignee_name=assignee_name,
        source_platform="telegram",
        work_category=work_category,
        status=status,
        priority=priority,
    )
    db.add(task)
    db.flush()
    return task


def write_calendar_mock_file() -> None:
    now = datetime.utcnow()
    payload = [
        {
            "id": "seed-evt-1",
            "title": "客户需求对齐会",
            "start_at": (now + timedelta(hours=2)).replace(microsecond=0).isoformat(),
            "end_at": (now + timedelta(hours=3)).replace(microsecond=0).isoformat(),
            "location": "上海静安",
            "attendees": ["alice@example.com", "ted@example.com"],
        },
        {
            "id": "seed-evt-2",
            "title": "项目周例会",
            "start_at": (now + timedelta(days=1, hours=1)).replace(microsecond=0).isoformat(),
            "end_at": (now + timedelta(days=1, hours=2)).replace(microsecond=0).isoformat(),
            "location": "线上会议",
            "attendees": ["bob@example.com", "ted@example.com"],
        },
    ]
    path = Path(settings.google_calendar_mock_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def seed_demo_data() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        now = datetime.utcnow().replace(microsecond=0)
        alice = upsert_contact(
            db,
            platform="telegram",
            platform_user_id="seed_alice",
            display_name="Alice Zhang",
            tags={"manual": ["vip"], "ai": ["work"], "pending": ["follow_up"]},
        )
        bob = upsert_contact(
            db,
            platform="telegram",
            platform_user_id="seed_bob",
            display_name="Bob Li",
            tags={"manual": [], "ai": ["partner"], "pending": ["finance"]},
        )
        cathy = upsert_contact(
            db,
            platform="telegram",
            platform_user_id="seed_cathy",
            display_name="Cathy Wu",
            tags={"manual": ["friend"], "ai": [], "pending": ["travel"]},
        )

        conv_alice = upsert_conversation(db, "telegram", "seed_chat_alice", alice.id, "Alice")
        conv_bob = upsert_conversation(db, "telegram", "seed_chat_bob", bob.id, "Bob")
        conv_cathy = upsert_conversation(db, "telegram", "seed_chat_cathy", cathy.id, "Cathy")

        messages = [
            upsert_message(
                db,
                conv_alice.id,
                "seed_msg_1",
                "请明天下午前跟进合同修改，并同步项目里程碑。",
                now - timedelta(hours=3),
            ),
            upsert_message(
                db,
                conv_bob.id,
                "seed_msg_2",
                "Need follow up on invoice and payment task this week.",
                now - timedelta(hours=2),
            ),
            upsert_message(
                db,
                conv_cathy.id,
                "seed_msg_3",
                "周末要不要一起去苏州？",
                now - timedelta(hours=1),
            ),
        ]

        for msg in messages:
            if msg.ai_processed_at is None:
                apply_message_insights(db, msg)

        upsert_task(
            db,
            title="准备客户A报价说明",
            due_at=now + timedelta(hours=8),
            assignee_name="Ted",
            work_category="sales",
            priority=2,
        )
        upsert_task(
            db,
            title="整理项目周报",
            due_at=now + timedelta(days=1, hours=4),
            assignee_name="Ted",
            work_category="operations",
            priority=3,
        )
        upsert_task(
            db,
            title="审核供应商付款单",
            due_at=now + timedelta(days=2),
            assignee_name="Finance",
            work_category="finance",
            status=TaskStatus.IN_PROGRESS,
            priority=2,
        )

        write_calendar_mock_file()
        db.commit()

        sync_google_calendar(db)
        generate_daily_summary(db)

        contacts = db.query(Contact).count()
        conversations = db.query(Conversation).count()
        messages_count = db.query(Message).count()
        tasks = db.query(Task).count()
        print(
            json.dumps(
                {
                    "ok": True,
                    "seeded": {
                        "contacts": contacts,
                        "conversations": conversations,
                        "messages": messages_count,
                        "tasks": tasks,
                    },
                    "calendar_mock_file": settings.google_calendar_mock_path,
                },
                ensure_ascii=False,
            )
        )
    finally:
        db.close()


if __name__ == "__main__":
    seed_demo_data()

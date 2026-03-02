from __future__ import annotations

from datetime import timedelta

from sqlalchemy.orm import Session

from app.models import Contact, Conversation, Message, Task, TaskStatus


def test_approve_pending_tags(client, db: Session, now) -> None:
    contact = Contact(
        platform="telegram",
        platform_user_id="u-1",
        display_name="Alice",
        tags_json={"manual": ["vip"], "ai": [], "pending": ["work", "friend"]},
        first_seen_at=now,
        last_seen_at=now,
    )
    db.add(contact)
    db.commit()

    response = client.post(f"/api/contacts/{contact.id}/tags/approve-pending")
    assert response.status_code == 200
    body = response.json()
    assert sorted(body["tags_json"]["manual"]) == ["friend", "vip", "work"]
    assert body["tags_json"]["pending"] == []


def test_tasks_filter_by_platform_and_work_category(client, db: Session, now) -> None:
    db.add_all(
        [
            Task(
                title="Telegram work task",
                status=TaskStatus.TODO,
                due_at=now + timedelta(days=1),
                source_platform="telegram",
                work_category="general_work",
            ),
            Task(
                title="Calendar task",
                status=TaskStatus.TODO,
                due_at=now + timedelta(days=2),
                source_platform="calendar",
                work_category="operations",
            ),
        ]
    )
    db.commit()

    response = client.get("/api/tasks", params={"source_platform": "telegram", "work_category": "general_work"})
    assert response.status_code == 200
    rows = response.json()
    assert len(rows) == 1
    assert rows[0]["title"] == "Telegram work task"


def test_overview_contains_platform_and_work_category_counts(client, db: Session, now) -> None:
    contact = Contact(
        platform="telegram",
        platform_user_id="u-2",
        display_name="Bob",
        tags_json={"manual": ["work"], "ai": ["priority"], "pending": []},
        first_seen_at=now,
        last_seen_at=now,
    )
    db.add(contact)
    db.flush()

    conversation = Conversation(platform="telegram", platform_chat_id="chat-2", contact_id=contact.id, title="Bob")
    db.add(conversation)
    db.flush()

    db.add(
        Message(
            conversation_id=conversation.id,
            platform_message_id="m-1",
            sender_role="contact",
            content="Please follow up the project meeting tomorrow",
            sent_at=now,
            raw_payload_json={},
        )
    )
    db.add(
        Task(
            title="Follow up meeting",
            status=TaskStatus.TODO,
            due_at=now + timedelta(hours=4),
            source_platform="telegram",
            work_category="general_work",
        )
    )
    db.commit()

    response = client.get("/api/dashboard/overview")
    assert response.status_code == 200
    body = response.json()
    assert body["platform_counts"]["telegram"] == 1
    assert body["work_category_counts"]["general_work"] == 1

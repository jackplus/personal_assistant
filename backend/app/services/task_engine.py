from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models import Task, TaskEvent, TaskStatus
from app.services.telegram_connector import send_telegram_message


def send_due_task_reminders(db: Session) -> dict[str, int]:
    now = datetime.utcnow()
    soon = now + timedelta(minutes=30)

    tasks = (
        db.query(Task)
        .filter(Task.status.in_([TaskStatus.TODO, TaskStatus.IN_PROGRESS, TaskStatus.BLOCKED]))
        .filter(Task.due_at.is_not(None), Task.due_at <= soon)
        .all()
    )

    sent = 0
    for task in tasks:
        already_sent = (
            db.query(TaskEvent)
            .filter(TaskEvent.task_id == task.id, TaskEvent.event_type == "reminder_sent")
            .first()
        )
        if already_sent:
            continue

        text = f"[Task Reminder] {task.title} due at {task.due_at.isoformat()}"
        delivered = send_telegram_message(text)
        db.add(
            TaskEvent(
                task_id=task.id,
                event_type="reminder_sent",
                payload_json={"delivered": delivered, "at": now.isoformat()},
            )
        )
        if delivered:
            sent += 1

    db.commit()
    return {"checked": len(tasks), "sent": sent}

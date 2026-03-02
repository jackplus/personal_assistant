from __future__ import annotations

from datetime import date, datetime

from sqlalchemy.orm import Session

from app.models import DailySummary, Message, Task, TaskStatus


def generate_daily_summary(db: Session, summary_date: date | None = None) -> DailySummary:
    summary_date = summary_date or datetime.utcnow().date()
    start = datetime.combine(summary_date, datetime.min.time())
    end = datetime.combine(summary_date, datetime.max.time())

    tasks_today = (
        db.query(Task)
        .filter(Task.due_at.is_not(None), Task.due_at >= start, Task.due_at <= end)
        .order_by(Task.due_at.asc())
        .all()
    )
    open_tasks = db.query(Task).filter(Task.status.in_([TaskStatus.TODO, TaskStatus.IN_PROGRESS, TaskStatus.BLOCKED])).count()
    recent_msgs = (
        db.query(Message)
        .filter(Message.sent_at >= start, Message.sent_at <= end)
        .order_by(Message.sent_at.desc())
        .limit(5)
        .all()
    )

    lines = [
        f"Daily Summary - {summary_date.isoformat()}",
        f"Open tasks: {open_tasks}",
        f"Tasks due today: {len(tasks_today)}",
    ]
    for task in tasks_today[:10]:
        lines.append(f"- [{task.status.value}] {task.title} @ {task.due_at.isoformat() if task.due_at else 'N/A'}")

    if recent_msgs:
        lines.append("Recent key messages:")
        for msg in recent_msgs:
            lines.append(f"- {msg.content[:80]}")

    content = "\n".join(lines)

    existing = db.query(DailySummary).filter(DailySummary.summary_date == summary_date).first()
    if existing:
        existing.content = content
        existing.generated_at = datetime.utcnow()
        summary = existing
    else:
        summary = DailySummary(summary_date=summary_date, content=content, generated_at=datetime.utcnow())
        db.add(summary)

    db.commit()
    db.refresh(summary)
    return summary

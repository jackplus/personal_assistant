from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.db import get_db
from app.models import CalendarEvent, Contact, Conversation, DailySummary, Message, Task, TaskStatus
from app.schemas import CalendarEventOut, ContactOut, ContactTagsUpdate, OverviewOut, TaskCreate, TaskOut, TaskPatch
from app.services.calendar_sync import sync_google_calendar
from app.services.summary_service import generate_daily_summary
from app.services.telegram_connector import sync_telegram_updates

router = APIRouter(prefix="/api")


@router.get("/dashboard/overview", response_model=OverviewOut)
def get_overview(db: Session = Depends(get_db)) -> OverviewOut:
    today = datetime.utcnow().date()
    start = datetime.combine(today, datetime.min.time())
    end = datetime.combine(today, datetime.max.time())

    tasks_today = (
        db.query(Task)
        .filter(Task.due_at.is_not(None), Task.due_at >= start, Task.due_at <= end)
        .order_by(Task.due_at.asc())
        .all()
    )
    overdue = (
        db.query(Task)
        .filter(Task.status.in_([TaskStatus.TODO, TaskStatus.IN_PROGRESS, TaskStatus.BLOCKED]))
        .filter(Task.due_at.is_not(None), Task.due_at < datetime.utcnow())
        .order_by(Task.due_at.asc())
        .all()
    )

    recent_messages = (
        db.query(Message)
        .options(joinedload(Message.conversation).joinedload(Conversation.contact))
        .order_by(Message.sent_at.desc())
        .limit(10)
        .all()
    )

    counts: dict[str, int] = {}
    contacts = db.query(Contact).all()
    for c in contacts:
        tags = c.tags_json or {}
        for key in ["manual", "ai", "pending"]:
            for tag in tags.get(key, []):
                counts[tag] = counts.get(tag, 0) + 1

    platform_counts_rows = (
        db.query(Conversation.platform, func.count(Message.id))
        .join(Message, Message.conversation_id == Conversation.id)
        .group_by(Conversation.platform)
        .all()
    )
    platform_counts = {platform: count for platform, count in platform_counts_rows}

    work_category_counts_rows = (
        db.query(func.coalesce(Task.work_category, "uncategorized"), func.count(Task.id))
        .group_by(func.coalesce(Task.work_category, "uncategorized"))
        .all()
    )
    work_category_counts = {category: count for category, count in work_category_counts_rows}

    summary = db.query(DailySummary).order_by(DailySummary.summary_date.desc()).first()

    return OverviewOut(
        contact_tag_counts=counts,
        platform_counts=platform_counts,
        work_category_counts=work_category_counts,
        today_tasks=[TaskOut.model_validate(t) for t in tasks_today],
        overdue_tasks=[TaskOut.model_validate(t) for t in overdue],
        recent_messages=[
            {
                "id": m.id,
                "content": m.content,
                "sent_at": m.sent_at.isoformat(),
                "conversation_id": m.conversation_id,
                "contact_name": m.conversation.contact.display_name if m.conversation and m.conversation.contact else None,
            }
            for m in recent_messages
        ],
        latest_summary=summary,
    )


@router.get("/contacts", response_model=list[ContactOut])
def list_contacts(tag: str | None = None, db: Session = Depends(get_db)) -> list[ContactOut]:
    contacts = db.query(Contact).order_by(Contact.last_seen_at.desc()).all()
    if tag:
        filtered = []
        for c in contacts:
            tags = c.tags_json or {}
            if tag in set(tags.get("manual", []) + tags.get("ai", []) + tags.get("pending", [])):
                filtered.append(c)
        contacts = filtered
    return [ContactOut.model_validate(c) for c in contacts]


@router.post("/contacts/{contact_id}/tags", response_model=ContactOut)
def update_contact_tags(contact_id: int, payload: ContactTagsUpdate, db: Session = Depends(get_db)) -> ContactOut:
    contact = db.query(Contact).filter(Contact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="contact not found")
    existing = contact.tags_json or {"manual": [], "ai": [], "pending": []}
    existing["manual"] = sorted(set(payload.tags))
    contact.tags_json = existing
    db.commit()
    db.refresh(contact)
    return ContactOut.model_validate(contact)


@router.post("/contacts/{contact_id}/tags/approve-pending", response_model=ContactOut)
def approve_pending_contact_tags(contact_id: int, db: Session = Depends(get_db)) -> ContactOut:
    contact = db.query(Contact).filter(Contact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="contact not found")

    existing = contact.tags_json or {"manual": [], "ai": [], "pending": []}
    manual = set(existing.get("manual", []))
    pending = set(existing.get("pending", []))
    existing["manual"] = sorted(manual | pending)
    existing["pending"] = []
    contact.tags_json = existing
    db.commit()
    db.refresh(contact)
    return ContactOut.model_validate(contact)


@router.get("/tasks", response_model=list[TaskOut])
def list_tasks(
    status: TaskStatus | None = None,
    assignee_name: str | None = None,
    due_before: datetime | None = None,
    source_platform: str | None = None,
    work_category: str | None = None,
    db: Session = Depends(get_db),
) -> list[TaskOut]:
    query = db.query(Task).order_by(Task.created_at.desc())
    if status:
        query = query.filter(Task.status == status)
    if assignee_name:
        query = query.filter(Task.assignee_name == assignee_name)
    if due_before:
        query = query.filter(Task.due_at.is_not(None), Task.due_at <= due_before)
    if source_platform:
        query = query.filter(Task.source_platform == source_platform)
    if work_category:
        if work_category == "uncategorized":
            query = query.filter(Task.work_category.is_(None))
        else:
            query = query.filter(Task.work_category == work_category)
    return [TaskOut.model_validate(t) for t in query.all()]


@router.post("/tasks", response_model=TaskOut)
def create_task(payload: TaskCreate, db: Session = Depends(get_db)) -> TaskOut:
    task = Task(**payload.model_dump())
    db.add(task)
    db.commit()
    db.refresh(task)
    return TaskOut.model_validate(task)


@router.patch("/tasks/{task_id}", response_model=TaskOut)
def patch_task(task_id: int, payload: TaskPatch, db: Session = Depends(get_db)) -> TaskOut:
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="task not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(task, key, value)
    db.commit()
    db.refresh(task)
    return TaskOut.model_validate(task)


@router.get("/calendar/events", response_model=list[CalendarEventOut])
def list_calendar_events(db: Session = Depends(get_db)) -> list[CalendarEventOut]:
    events = db.query(CalendarEvent).order_by(CalendarEvent.start_at.asc()).all()
    output: list[CalendarEventOut] = []
    for e in events:
        output.append(
            CalendarEventOut(
                id=f"calendar:{e.id}",
                source="google_calendar",
                title=e.title,
                start_at=e.start_at,
                end_at=e.end_at,
                location=e.location,
            )
        )

    due_tasks = db.query(Task).filter(Task.due_at.is_not(None)).all()
    for task in due_tasks:
        output.append(
            CalendarEventOut(
                id=f"task:{task.id}",
                source="task_due",
                title=f"Task Due: {task.title}",
                start_at=task.due_at,
                end_at=task.due_at,
                location=task.location,
            )
        )
    return sorted(output, key=lambda x: x.start_at)


@router.post("/sync/telegram")
def manual_sync_telegram(db: Session = Depends(get_db)) -> dict:
    return sync_telegram_updates(db)


@router.post("/sync/calendar")
def manual_sync_calendar(db: Session = Depends(get_db)) -> dict:
    return sync_google_calendar(db)


@router.post("/summary/daily")
def manual_daily_summary(db: Session = Depends(get_db)) -> dict:
    summary = generate_daily_summary(db)
    return {
        "summary_date": summary.summary_date.isoformat(),
        "generated_at": summary.generated_at.isoformat(),
        "content": summary.content,
    }


@router.get("/data/export")
def data_export(db: Session = Depends(get_db)) -> dict:
    return {
        "contacts": db.query(func.count(Contact.id)).scalar() or 0,
        "conversations": db.query(func.count(Conversation.id)).scalar() or 0,
        "messages": db.query(func.count(Message.id)).scalar() or 0,
        "tasks": db.query(func.count(Task.id)).scalar() or 0,
    }


@router.post("/data/purge")
def data_purge() -> dict:
    raise HTTPException(status_code=501, detail="not implemented in MVP")

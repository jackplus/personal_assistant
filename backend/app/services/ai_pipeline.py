from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.config import settings
from app.models import Contact, Message, Task


@dataclass
class ExtractedTask:
    title: str
    description: str | None = None
    due_at: datetime | None = None
    location: str | None = None
    assignee_name: str | None = None
    priority: int = 3


@dataclass
class MessageInsights:
    is_work_related: bool
    work_category: str
    extracted_tasks: list[ExtractedTask]
    suggested_contact_tags: list[str]
    confidence: float


def _heuristic_due_at(text: str) -> datetime | None:
    lower = text.lower()
    now = datetime.utcnow()
    if "tomorrow" in lower or "明天" in text:
        return now + timedelta(days=1)
    if "today" in lower or "今天" in text:
        return now + timedelta(hours=8)
    return None


def _heuristic_analyze(text: str) -> MessageInsights:
    lower = text.lower()
    is_work = any(k in lower for k in ["todo", "task", "deadline", "project", "follow up", "meeting"]) or any(
        k in text for k in ["任务", "项目", "截止", "跟进", "会议", "待办"]
    )
    tags = ["work"] if is_work else ["personal"]
    extracted_tasks: list[ExtractedTask] = []
    if is_work and any(k in lower for k in ["please", "need", "todo", "follow up"]) or any(k in text for k in ["请", "需要", "安排", "跟进"]):
        clean = re.sub(r"\s+", " ", text).strip()
        title = clean[:80] if clean else "Follow up"
        extracted_tasks.append(ExtractedTask(title=title, due_at=_heuristic_due_at(text)))
    return MessageInsights(
        is_work_related=is_work,
        work_category="general_work" if is_work else "non_work",
        extracted_tasks=extracted_tasks,
        suggested_contact_tags=tags,
        confidence=0.55,
    )


def _openai_analyze(text: str) -> MessageInsights | None:
    if not settings.openai_api_key:
        return None
    try:
        from openai import OpenAI

        client = OpenAI(api_key=settings.openai_api_key)
        prompt = (
            "You are an assistant extracting structured insights from a chat message. "
            "Return strict JSON with keys: is_work_related(boolean), work_category(string), "
            "suggested_contact_tags(array of string), confidence(number 0-1), "
            "extracted_tasks(array of objects with title,description,due_at_iso,location,assignee_name,priority)."
        )
        response = client.responses.create(
            model=settings.openai_model,
            input=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": text},
            ],
        )
        raw = response.output_text
        data = json.loads(raw)
        extracted = []
        for item in data.get("extracted_tasks", []):
            due_at = None
            if item.get("due_at_iso"):
                try:
                    due_at = datetime.fromisoformat(item["due_at_iso"].replace("Z", "+00:00")).replace(tzinfo=None)
                except ValueError:
                    due_at = None
            extracted.append(
                ExtractedTask(
                    title=item.get("title", "Untitled Task"),
                    description=item.get("description"),
                    due_at=due_at,
                    location=item.get("location"),
                    assignee_name=item.get("assignee_name"),
                    priority=int(item.get("priority", 3)),
                )
            )
        return MessageInsights(
            is_work_related=bool(data.get("is_work_related", False)),
            work_category=str(data.get("work_category", "general_work")),
            extracted_tasks=extracted,
            suggested_contact_tags=[str(x) for x in data.get("suggested_contact_tags", [])],
            confidence=float(data.get("confidence", 0.5)),
        )
    except Exception:
        return None


def analyze_message(text: str) -> MessageInsights:
    return _openai_analyze(text) or _heuristic_analyze(text)


def merge_contact_tags(contact: Contact, ai_tags: list[str], confidence: float) -> None:
    existing = contact.tags_json or {}
    manual = set(existing.get("manual", []))
    ai_existing = set(existing.get("ai", []))
    pending = set(existing.get("pending", []))

    if confidence >= 0.7:
        ai_existing.update(ai_tags)
        pending.difference_update(ai_tags)
    else:
        pending.update(ai_tags)

    contact.tags_json = {
        "manual": sorted(manual),
        "ai": sorted(ai_existing),
        "pending": sorted(pending - manual),
    }


def apply_message_insights(db: Session, message: Message) -> MessageInsights:
    insights = analyze_message(message.content)
    merge_contact_tags(message.conversation.contact, insights.suggested_contact_tags, insights.confidence)

    for extracted in insights.extracted_tasks:
        duplicate = (
            db.query(Task)
            .filter(Task.source_message_id == message.id, Task.title == extracted.title)
            .first()
        )
        if duplicate:
            continue
        db.add(
            Task(
                title=extracted.title,
                description=extracted.description,
                due_at=extracted.due_at,
                location=extracted.location,
                assignee_name=extracted.assignee_name,
                priority=extracted.priority,
                source_platform=message.conversation.platform,
                work_category=insights.work_category,
                source_message_id=message.id,
            )
        )

    message.ai_processed_at = datetime.utcnow()
    return insights

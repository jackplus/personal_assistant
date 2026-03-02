from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models import TaskStatus


class ContactOut(BaseModel):
    id: int
    platform: str
    platform_user_id: str
    display_name: str
    tags_json: dict
    last_seen_at: datetime

    model_config = {"from_attributes": True}


class ContactTagsUpdate(BaseModel):
    tags: list[str] = Field(default_factory=list)


class TaskCreate(BaseModel):
    title: str
    description: str | None = None
    priority: int = 3
    due_at: datetime | None = None
    location: str | None = None
    assignee_name: str | None = None
    work_category: str | None = None


class TaskPatch(BaseModel):
    status: TaskStatus | None = None
    priority: int | None = None
    due_at: datetime | None = None
    location: str | None = None
    assignee_name: str | None = None
    description: str | None = None
    title: str | None = None
    work_category: str | None = None


class TaskOut(BaseModel):
    id: int
    title: str
    description: str | None
    status: TaskStatus
    priority: int
    due_at: datetime | None
    location: str | None
    assignee_name: str | None
    source_platform: str
    work_category: str | None
    source_message_id: int | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CalendarEventOut(BaseModel):
    id: str
    source: str
    title: str
    start_at: datetime
    end_at: datetime
    location: str | None = None


class DailySummaryOut(BaseModel):
    summary_date: date
    content: str
    generated_at: datetime

    model_config = {"from_attributes": True}


class OverviewOut(BaseModel):
    contact_tag_counts: dict[str, int]
    platform_counts: dict[str, int]
    work_category_counts: dict[str, int]
    today_tasks: list[TaskOut]
    overdue_tasks: list[TaskOut]
    recent_messages: list[dict]
    latest_summary: DailySummaryOut | None

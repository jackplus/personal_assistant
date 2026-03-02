from __future__ import annotations

from datetime import date, datetime
from enum import Enum

from sqlalchemy import JSON, Date, DateTime, Enum as SAEnum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class TaskStatus(str, Enum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    DONE = "done"
    CANCELLED = "cancelled"


class Contact(Base):
    __tablename__ = "contacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    platform: Mapped[str] = mapped_column(String(32), index=True)
    platform_user_id: Mapped[str] = mapped_column(String(128), index=True)
    display_name: Mapped[str] = mapped_column(String(255))
    tags_json: Mapped[dict] = mapped_column(JSON, default=dict)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    conversations: Mapped[list[Conversation]] = relationship(back_populates="contact")

    __table_args__ = (UniqueConstraint("platform", "platform_user_id", name="uq_contact_platform_user"),)


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    platform: Mapped[str] = mapped_column(String(32), index=True)
    platform_chat_id: Mapped[str] = mapped_column(String(128), index=True)
    contact_id: Mapped[int] = mapped_column(ForeignKey("contacts.id"), index=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)

    contact: Mapped[Contact] = relationship(back_populates="conversations")
    messages: Mapped[list[Message]] = relationship(back_populates="conversation")

    __table_args__ = (UniqueConstraint("platform", "platform_chat_id", name="uq_conversation_platform_chat"),)


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id"), index=True)
    platform_message_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    sender_role: Mapped[str] = mapped_column(String(32), default="contact")
    content: Mapped[str] = mapped_column(Text)
    sent_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    raw_payload_json: Mapped[dict] = mapped_column(JSON, default=dict)
    ai_processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    conversation: Mapped[Conversation] = relationship(back_populates="messages")
    tasks: Mapped[list[Task]] = relationship(back_populates="source_message")

    __table_args__ = (UniqueConstraint("conversation_id", "platform_message_id", name="uq_message_platform_id"),)


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_message_id: Mapped[int | None] = mapped_column(ForeignKey("messages.id"), nullable=True, index=True)
    status: Mapped[TaskStatus] = mapped_column(SAEnum(TaskStatus), default=TaskStatus.TODO, index=True)
    priority: Mapped[int] = mapped_column(Integer, default=3)
    due_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    assignee_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_platform: Mapped[str] = mapped_column(String(32), default="telegram", index=True)
    work_category: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    source_message: Mapped[Message | None] = relationship(back_populates="tasks")
    events: Mapped[list[TaskEvent]] = relationship(back_populates="task")


class TaskEvent(Base):
    __tablename__ = "task_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    task: Mapped[Task] = relationship(back_populates="events")


class CalendarEvent(Base):
    __tablename__ = "calendar_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider: Mapped[str] = mapped_column(String(32), default="google", index=True)
    provider_event_id: Mapped[str] = mapped_column(String(255), index=True)
    title: Mapped[str] = mapped_column(String(255))
    start_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    end_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    attendees_json: Mapped[list] = mapped_column(JSON, default=list)
    synced_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("provider", "provider_event_id", name="uq_provider_event"),)


class DailySummary(Base):
    __tablename__ = "daily_summaries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    summary_date: Mapped[date] = mapped_column(Date, unique=True)
    content: Mapped[str] = mapped_column(Text)
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AppState(Base):
    __tablename__ = "app_state"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

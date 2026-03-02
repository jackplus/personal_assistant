from __future__ import annotations

from apscheduler.schedulers.background import BackgroundScheduler

from app.db import SessionLocal
from app.services.calendar_sync import sync_google_calendar
from app.services.summary_service import generate_daily_summary
from app.services.task_engine import send_due_task_reminders
from app.services.telegram_connector import sync_telegram_updates


scheduler = BackgroundScheduler(timezone="UTC")


def _job_sync_telegram() -> None:
    db = SessionLocal()
    try:
        sync_telegram_updates(db)
    finally:
        db.close()


def _job_sync_calendar() -> None:
    db = SessionLocal()
    try:
        sync_google_calendar(db)
    finally:
        db.close()


def _job_reminders() -> None:
    db = SessionLocal()
    try:
        send_due_task_reminders(db)
    finally:
        db.close()


def _job_daily_summary() -> None:
    db = SessionLocal()
    try:
        generate_daily_summary(db)
    finally:
        db.close()


def start_scheduler() -> None:
    if scheduler.running:
        return
    scheduler.add_job(_job_sync_telegram, "interval", seconds=30, id="telegram_sync", replace_existing=True)
    scheduler.add_job(_job_sync_calendar, "interval", minutes=15, id="calendar_sync", replace_existing=True)
    scheduler.add_job(_job_reminders, "interval", minutes=1, id="task_reminders", replace_existing=True)
    scheduler.add_job(_job_daily_summary, "cron", hour=10, minute=0, id="daily_summary", replace_existing=True)
    scheduler.start()


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)

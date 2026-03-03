# Personal Assistant MVP

Local-first MVP for:
- Telegram message ingestion
- AI-based message classification and task extraction
- Contact tagging
- Task assignment/status tracking
- Calendar timeline view
- Due-task reminders via Telegram bot

## Project structure

- `backend/`: FastAPI + SQLAlchemy + SQLite + APScheduler
- `frontend/`: React + Vite + Ant Design dashboard

## Backend quick start

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

## Frontend quick start

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

Open dashboard at `http://127.0.0.1:5173`.

## Seed demo data

```bash
cd backend
source .venv/bin/activate
PYTHONPATH=. python scripts/seed_demo_data.py
```

## Main API endpoints

- `GET /api/dashboard/overview`
- `GET /api/contacts`
- `POST /api/contacts/{id}/tags`
- `POST /api/contacts/{id}/tags/approve-pending`
- `GET /api/tasks`
- `GET /api/tasks?source_platform=telegram&work_category=general_work`
- `GET /api/tasks/{id}/details`
- `POST /api/tasks`
- `PATCH /api/tasks/{id}`
- `GET /api/calendar/events`
- `POST /api/sync/telegram`
- `POST /api/sync/telegram/user`
- `POST /api/sync/calendar`
- `POST /api/summary/daily`
- `GET /api/data/export`
- `POST /api/data/purge` (reserved; 501 in MVP)

## Notes

- Google Calendar is mocked through `backend/data/google_calendar_mock.json` in this MVP.
- Telegram polling uses bot `getUpdates` with offset persistence in DB.
- For real Telegram account sync, use Telegram User API (Telethon) with `TELEGRAM_USER_*` env vars and trigger `/api/sync/telegram/user`.
- If `OPENAI_API_KEY` is not configured, a heuristic parser is used.

## Real Telegram Account Validation

1. Create Telegram app credentials at `https://my.telegram.org` (`api_id`, `api_hash`).
2. Generate a String Session:

```bash
cd backend
source .venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=. python scripts/generate_telegram_user_session.py
```

3. Configure `backend/.env`:

```bash
TELEGRAM_SYNC_MODE=user
TELEGRAM_USER_API_ID=...
TELEGRAM_USER_API_HASH=...
TELEGRAM_USER_STRING_SESSION=...
TELEGRAM_USER_DIALOG_LIMIT=30
TELEGRAM_USER_MESSAGE_LIMIT=100
TELEGRAM_USER_INCLUDE_OUTGOING=false
```

4. Restart backend and click `Sync Telegram User` in dashboard, or call:

```bash
curl -X POST http://127.0.0.1:8000/api/sync/telegram/user
```

Note: This sync scans recent messages in your dialogs by configured limits (dialog/message limits), then applies tagging/task extraction for incoming text messages.

## Documentation

- Next-step guide (CN): `docs/PHASE1_NEXT_STEPS_GUIDE.md`

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
- `POST /api/tasks`
- `PATCH /api/tasks/{id}`
- `GET /api/calendar/events`
- `POST /api/sync/telegram`
- `POST /api/sync/calendar`
- `POST /api/summary/daily`
- `GET /api/data/export`
- `POST /api/data/purge` (reserved; 501 in MVP)

## Notes

- Google Calendar is mocked through `backend/data/google_calendar_mock.json` in this MVP.
- Telegram polling uses bot `getUpdates` with offset persistence in DB.
- If `OPENAI_API_KEY` is not configured, a heuristic parser is used.

## Documentation

- Next-step guide (CN): `docs/PHASE1_NEXT_STEPS_GUIDE.md`

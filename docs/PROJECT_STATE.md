# FleetOps Project State

This file is the current working state of the project. Update it after each meaningful step and before starting a new large phase or clearing Claude Code context.

---

## Current Phase

Step 2 — Backend + DB foundation (FastAPI config, PostgreSQL connection, SQLAlchemy async session, Alembic setup). Still in progress: Redis and `/health` connectivity reporting are not done yet.

---

## Completed

### Step 1 — Initial project structure ✓

- Full monorepo folder structure created (backend, frontend, simulator, infra, docs).
- Minimal FastAPI app with `GET /health → {"status": "ok"}` verified live.
- Pytest test passes: `tests/test_health.py::test_health_returns_ok`.
- `requirements.txt`, `requirements-dev.txt`, `.env.example` in place.
- `docker-compose.yml` skeleton (services declared, not yet fully wired).
- `.gitignore` at repo root.

### Step 2 — Backend + DB foundation (partial) ✓

- Typed `Settings` config via `pydantic-settings` (`app_name`, `environment`, `debug`, `api_prefix`).
- `DATABASE_URL` added to `Settings` with an async-ready default (`postgresql+asyncpg://...`).
- Docker Postgres service running and verified reachable.
- SQLAlchemy async engine + `async_sessionmaker` session foundation (`app/db/session.py`).
- `check_db_connection()` runs `SELECT 1` and verified returning `True` against live Postgres.
- Alembic migration infrastructure in place (`alembic.ini`, async `env.py`, `script.py.mako`, empty `versions/`, shared `Base`).

---

## Key Decisions

- Backend is the only gatekeeper.
- Simulator talks only to the backend over REST.
- PostgreSQL stores durable historical/audit data.
- Redis stores fast operational/ephemeral data.
- Backend code uses layered structure: API routes, services, repositories, schemas, models, db, cache, sockets.
- Auth/RBAC are part of the final system but will be implemented only after the core flow is proven.
- `pydantic-settings` used for typed config from the start; `.env.example` seeds later-phase vars.
- Alembic reads the DB URL from `settings.database_url` (one source of truth); migrations run on the async engine.

---

## Current Working Proof

Run from `backend/`:

```text
python -m pytest tests/ -q
  → 7 passed

docker compose exec postgres psql -U fleetops -d fleetops -c "SELECT 1;"
  → 1

python -c "import asyncio; from app.db.session import check_db_connection; print(asyncio.run(check_db_connection()))"
  → True

python -m alembic current
  → runs with no error (no migrations applied yet)
```

`GET /health → {"status": "ok"}` (HTTP 200) still serves via `python -m uvicorn app.main:app --reload`.

---

## Known Issues / Not Implemented Yet

- Redis client not implemented.
- `/health` does not yet report DB/Redis status (still returns only `{"status": "ok"}`).
- No SQLAlchemy business models yet (`Base.metadata` is empty).
- No real migrations yet (`alembic/versions/` is empty).
- No telemetry ingestion.
- No WebSocket/Socket.IO implementation.
- No simulator behavior.
- No frontend UI.
- No auth/JWT/RBAC.

---

## Next Step

The next checkpoint will be chosen before implementation — either:

- Redis client foundation, or
- First DB model + first real Alembic migration.

Do not decide broadly here; the specific next checkpoint will be selected at the start of the next step.

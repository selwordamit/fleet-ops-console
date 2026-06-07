# FleetOps Project State

This file is the current working state of the project. Update it after each meaningful step and before starting a new large phase or clearing Claude Code context.

---

## Current Phase

Step 2 — Backend + DB + Cache foundation (FastAPI config, PostgreSQL connection, Redis connection, Alembic setup).

---

## Completed

### Step 1 — Initial project structure ✓

- Full monorepo folder structure created (backend, frontend, simulator, infra, docs).
- Minimal FastAPI app with `GET /health → {"status": "ok"}` verified live.
- Pytest test passes: `tests/test_health.py::test_health_returns_ok`.
- `requirements.txt`, `requirements-dev.txt`, `.env.example` in place.
- `docker-compose.yml` skeleton (services declared, not yet wired).
- `.gitignore` at repo root.

---

## Key Decisions

- Backend is the only gatekeeper.
- Simulator talks only to the backend over REST.
- PostgreSQL stores durable historical/audit data.
- Redis stores fast operational/ephemeral data.
- Backend code uses layered structure: API routes, services, repositories, schemas, models, db, cache, sockets.
- Auth/RBAC are part of the final system but will be implemented only after the core flow is proven.
- `pydantic-settings` used for typed config from the start; `.env.example` seeds Phase 02 vars.

---

## Current Working Proof

```text
GET /health → {"status": "ok"}   (HTTP 200)
python -m pytest tests/test_health.py  →  1 passed
```

Run from `backend/`:

```powershell
python -m uvicorn app.main:app --reload
```

---

## Known Issues / Not Implemented Yet

- Docker Compose services are skeleton only (no Dockerfiles, no env wiring).
- No PostgreSQL connection.
- No Redis connection.
- No SQLAlchemy models.
- No Alembic migrations.
- No telemetry ingestion.
- No WebSocket/Socket.IO.
- No simulator behavior.
- No frontend UI.
- No auth/JWT/RBAC.

---

## Next Step

Step 2: Add typed `Settings` (pydantic-settings), async PostgreSQL engine (SQLAlchemy + asyncpg), Redis client (redis-py async), SQLAlchemy session factory, and Alembic init. Extend `/health` to report DB and Redis connectivity. Verify in Postman.

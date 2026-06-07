# Phase 01 — Project Structure

## Goal

Create the initial monorepo structure and minimal backend health endpoint without implementing business logic.

---

## Scope

Implement only:

- root project structure
- backend folder structure
- frontend folder structure
- simulator folder structure
- docs folder structure
- minimal FastAPI app
- `GET /health -> { "status": "ok" }`
- placeholder files where needed to keep folders

---

## Out of Scope

Do not implement yet:

- auth
- JWT
- RBAC
- database models
- SQLAlchemy
- Alembic
- Redis
- telemetry ingestion
- WebSocket
- simulator behavior
- frontend UI
- alert rules
- commands
- performance work

---

## Why This Phase Comes First

The project has multiple services and many moving parts. Before building features, the boundaries must be clear:

- backend owns validation and business logic
- frontend owns UI and rendering
- simulator acts like an external producer
- docs track decisions and progress
- infrastructure will later connect the services

A clean structure makes every future class and file easier to justify.

---

## Verification

After implementation, verify:

```bash
cd backend
uvicorn app.main:app --reload
```

Then open:

```text
http://localhost:8000/health
```

Expected response:

```json
{
  "status": "ok"
}
```

---

## Team Lead Defense

If asked why this phase exists:

> I started by defining system boundaries before implementing features. This project has backend, frontend, simulator, database, Redis, and real-time communication. A clear folder structure prevents business logic from leaking into routes, database access from leaking into services, or simulator logic bypassing the backend.

If asked why not start with the database:

> Before persistence, I wanted to prove the backend skeleton runs and that the project structure is clear. The next step is adding config, PostgreSQL, Redis, and migrations.


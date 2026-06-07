# Fleet Operations Console

A real-time fleet operations console. Simulated vehicles continuously report telemetry: GPS position, speed, battery, and status. Operators watch them live on a map, receive real-time alerts when rules trip, and send commands back to vehicles with acknowledgements.

> **Source of truth:** the full project spec is `docs/project-spec.md`. When anything conflicts with this file, the project spec wins.

> **Architecture overview:** `docs/architecture.md` explains the service relationships, data flow, hierarchy, and scaling notes.

> **Decision tracking:** significant implementation decisions must be logged in `docs/decision-log.md`.

> **Progress tracking:** `docs/PROJECT_STATE.md` is the current working state of the project. Update it before starting a new large phase or clearing context.

---

## Stack

### Backend
- Python + FastAPI, async-native API framework.
- Uvicorn, ASGI server.
- python-socketio, Socket.IO/WebSocket real-time channel.
- Pydantic, request/response validation and OpenAPI schemas.

### Data
- PostgreSQL, primary durable database.
- Telemetry stored in PostgreSQL as historical, append-heavy time-series data, eventually using partitioning + retention.
- Redis for current-state cache, pub/sub fan-out, rate limiting, refresh-token store, and presence.
- SQLAlchemy async ORM + Alembic migrations.

### Frontend
- React + TypeScript with Vite.
- Leaflet + OpenStreetMap + marker clustering.
- Zustand for local/live client state.
- TanStack Query for server state fetched over REST.
- shadcn/ui for UI components.
- Recharts for charts.
- socket.io-client for the real-time channel.

### Auth
- JWT access + refresh tokens.
- RBAC roles: viewer, operator, admin.
- passlib + bcrypt for password hashing.

### Infra
- Simulator: Python service. It talks only to the backend over REST.
- Docker + Docker Compose.

---

## Build Order

Backend-first. Verify each step manually before moving on.

1. **Initial project structure** — create clear folder boundaries and a minimal `/health` endpoint.
2. **Backend + DB + Cache foundation** — FastAPI config, PostgreSQL connection, Redis connection, Alembic setup.
3. **Backend core telemetry flow** — Agent + Telemetry models, REST ingestion, Pydantic validation, Postgres persistence, Redis current-state cache. Verify in Postman.
4. **Current-state APIs** — list agents, get current state, get telemetry history.
5. **WebSocket contract and live push** — define message contract first, then push telemetry/alerts to clients.
6. **Client shell** — connect to backend, verify REST and Socket.IO communication.
7. **Map** — render map, then one static marker, then live markers.
8. **Simulator** — register fake agents and POST telemetry only through backend REST.
9. **Alerts** — rules, evaluation, persistence, WebSocket alert events.
10. **Commands** — command creation, pending state, simulator acknowledgement, WebSocket ACK.
11. **JWT + RBAC** — secure REST and WebSocket channels.
12. **Performance + reliability** — rate limiting, offline sweep, retention, load test, UI throttling.
13. **README + final defense** — decisions, demo script, what works, what was deferred.

Important: do not jump ahead. Each step should be small enough to verify before continuing.

---

## Project Structure

```text
backend/
  app/
    main.py
    core/              — config, logging, security later
    api/               — route handlers only
    models/            — SQLAlchemy persistence models
    schemas/           — Pydantic request/response/event schemas
    repositories/      — database access only
    services/          — business logic and orchestration
    db/                — SQLAlchemy engine/session setup
    cache/             — Redis client and key helpers
    sockets/           — Socket.IO server and event handlers
  alembic/             — database migrations
  tests/

frontend/
  src/
    api/               — REST client functions and TanStack Query hooks
    components/        — reusable UI components
    features/          — feature-specific UI modules
    stores/            — Zustand stores
    sockets/           — Socket.IO client wrapper
    types/             — shared TypeScript types
    pages/             — top-level pages

simulator/
  app/                 — Python simulator service

infra/                 — optional infra notes/scripts

docs/
  project-spec.md      — original project requirements
  architecture.md      — architecture and data-flow explanation
  decision-log.md      — implementation decisions
  PROJECT_STATE.md     — current progress and working proof
  phases/              — phase-specific notes
```

---

## Explainability-first development

This project prioritizes explainability over feature count.

Rules:
- Implement in small, reviewable steps.
- Do not add features outside the current phase.
- Prefer simple, explicit code over clever abstractions.
- Every new module/class/function must have a clear reason to exist.
- Add concise comments only when they explain WHY, not obvious WHAT.
- Use structured logging at meaningful system boundaries.
- Do not use print statements.
- After every implementation step, summarize:
  1. Files changed
  2. New modules/classes/functions
  3. Why each one exists
  4. What was intentionally not implemented
  5. How to verify

## Backend Rules

- Keep routes thin. Route handlers receive HTTP requests and call services.
- Business logic lives in `services/`, not in route handlers.
- Database access lives in `repositories/`, not directly in routes.
- Pydantic schemas validate every incoming payload.
- SQLAlchemy models represent persistence, not API contracts.
- No secrets in code. Use `.env` and typed settings.
- The simulator talks only to the backend API over REST. Never directly to PostgreSQL or Redis.
- PostgreSQL is the durable source of truth for historical and audit data.
- Redis is used for operational/ephemeral state: latest telemetry, pub/sub, presence, rate limits, refresh tokens.
- WebSocket must be authenticated in the final secured version, not only REST.
- Passwords are always hashed with bcrypt via passlib. Never store plaintext.
- Command status is always one of: `pending | acknowledged | failed | expired`.

---

## Frontend Rules

- REST/server state belongs in TanStack Query.
- Live operational state from Socket.IO belongs in Zustand.
- WebSocket message shapes are defined in one place: `frontend/src/types/socket.ts`.
- UI preferences such as map view, theme, and drafts may be persisted to localStorage.
- Command UI should be optimistic: show `pending` immediately, then resolve to `acknowledged`, `failed`, or `expired`.

---

## WebSocket Contract Rules

Before implementing the real-time channel, define the contract in `docs/ws-protocol.md`.

Envelope shape:

```json
{
  "type": "telemetry.updated",
  "payload": {},
  "ts": "2026-06-06T12:00:00Z",
  "requestId": "optional-correlation-id"
}
```

The backend Pydantic event schemas and frontend TypeScript types must match this document.

---

## Working With Claude Code

- Read `CLAUDE.md`, `docs/project-spec.md`, `docs/architecture.md`, and `docs/PROJECT_STATE.md` before starting a task.
- Use the docs as context, not permission to implement the entire system.
- Implement only the current requested step.
- Do not add extra features without being asked.
- Plan first, implement second, verify third, summarize fourth.
- After each step, return:
  1. Files changed.
  2. What was implemented.
  3. What was intentionally not implemented.
  4. How to verify.
  5. Any unclear or conflicting documentation.
  6. Suggested next step.
- New large phase = new session or `/clear`.
- Small fixes inside the same phase can stay in the same session.
- Before clearing context, update `docs/PROJECT_STATE.md`.
- Significant implementation decisions go into `docs/decision-log.md`.

---

## Development Safety Rules

During early implementation, selected routes may be temporarily unprotected so the core backend flow can be verified quickly in Postman. This is intentional.

Final target state:
- All routes except auth are protected by JWT.
- RBAC is enforced on protected REST endpoints.
- Socket.IO connection is authenticated.
- Socket.IO actions are role-checked.

Do not implement auth before the core telemetry, Redis, WebSocket, simulator, alerts, and commands flows are proven unless specifically instructed.

---

## Progress

Current authoritative progress is in `docs/PROJECT_STATE.md`.

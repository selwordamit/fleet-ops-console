# Stack Decisions

Why each major technology was chosen for the Fleet Operations Console, with alternatives, tradeoffs, and current implementation status.

Source of truth for requirements: `docs/onboarding-project-spec.md`. This file documents *technology choices*, not requirements.

Status legend: **implemented** = working and verified · **planned** = chosen but not built yet · **deferred** = intentionally postponed.

---

## Backend — Python + FastAPI (async)

- **Choice:** FastAPI as the async web framework.
- **Why it fits:** The system is real-time and I/O-bound (DB, cache, sockets). Async lets one worker handle many concurrent connections. FastAPI also gives Pydantic validation and OpenAPI for free.
- **Alternatives considered:** Django/DRF (sync-first, heavier), Flask (no native async or validation), Node/Express.
- **Tradeoff / cost:** Async code is harder to reason about; every DB/cache call must be awaited correctly.
- **Status:** implemented (base app + `/health` + typed settings).

## ASGI server — Uvicorn

- **Choice:** Uvicorn to run the ASGI app.
- **Why it fits:** Standard, lightweight ASGI server that pairs naturally with FastAPI and supports async and WebSockets.
- **Alternatives considered:** Hypercorn; Gunicorn with Uvicorn workers (a likely production step later).
- **Tradeoff / cost:** A single Uvicorn process is fine for dev; multi-worker scaling is a later concern.
- **Status:** implemented (used to serve the app).

## Real-time — python-socketio / Socket.IO

- **Choice:** Socket.IO via python-socketio for live telemetry, alerts, command ACKs, and presence.
- **Why it fits:** Built-in reconnect, event model, and a matching browser client reduce hand-rolled WebSocket plumbing. The spec calls for live updates and reconnect awareness.
- **Alternatives considered:** Raw WebSockets (more manual reconnect/multiplexing), Server-Sent Events (one-directional).
- **Tradeoff / cost:** Adds a protocol layer on top of WebSockets; both ends must agree on the message envelope.
- **Status:** planned.

## Database — PostgreSQL

- **Choice:** PostgreSQL as the durable source of truth.
- **Why it fits:** Relational integrity for users/agents/commands plus append-heavy telemetry that can later use native partitioning and retention.
- **Alternatives considered:** MySQL; a dedicated time-series DB (e.g. Timescale) — deferred as a possible later step.
- **Tradeoff / cost:** Telemetry volume will eventually need partitioning/retention work.
- **Status:** implemented. `agents` and `telemetry` tables exist and persist data. Telemetry is a single simple table for the MVP; native partitioning + retention are deferred and documented as a future scalability improvement.

## ORM & migrations — SQLAlchemy async + Alembic

- **Choice:** SQLAlchemy async (asyncpg driver) for DB access; Alembic for schema migrations.
- **Why it fits:** ORM/session structure matches a layered backend; Alembic gives versioned, reviewable schema changes and a reproducible DB.
- **Alternatives considered:** Raw asyncpg (no ORM/migrations), sync SQLAlchemy, Tortoise/SQLModel.
- **Tradeoff / cost:** Async sessions and the async Alembic `env.py` are more complex than their sync equivalents.
- **Status:** implemented (async engine/session + Alembic infrastructure; real migrations applied for the `agents` and `telemetry` tables).

## Cache / pub-sub — Redis

- **Choice:** Redis for latest-known-state cache, pub/sub fan-out, presence, rate limiting, and refresh-token storage.
- **Why it fits:** Fast ephemeral state and cross-worker pub/sub keep the map responsive without scanning telemetry history; clearly separated from Postgres's durable role.
- **Alternatives considered:** In-memory process state (does not scale across workers), Postgres LISTEN/NOTIFY.
- **Tradeoff / cost:** Another service to run; must keep cache/durable responsibilities distinct.
- **Status:** partial — connectivity implemented (async client + `check_redis_connection()`) and Redis is now used for **real latest-state writes** on telemetry ingestion (`agent:{id}:state`). Still planned: pub/sub fan-out, rate limiting, refresh-token store, presence, and offline detection.

## Auth — JWT access/refresh + RBAC

- **Choice:** JWT access + refresh tokens with role-based access control (viewer, operator, admin).
- **Why it fits:** Stateless access tokens let any worker validate requests; refresh tokens (stored in Redis) support revocation. Roles map directly to the spec's permission tiers.
- **Alternatives considered:** Server-side sessions, OAuth/third-party identity provider.
- **Tradeoff / cost:** Token lifecycle, refresh rotation, and revocation add complexity.
- **Status:** planned (intentionally after the core flow is proven).

## Password hashing — passlib + bcrypt

- **Choice:** passlib with bcrypt for password hashing.
- **Why it fits:** bcrypt is a vetted, salted, slow hash; passlib provides a clean interface. Spec requires hashed passwords, never plaintext.
- **Alternatives considered:** Argon2 (also strong; bcrypt chosen for ubiquity/simplicity).
- **Tradeoff / cost:** Bcrypt's work factor trades CPU for security and must be tuned.
- **Status:** planned.

## Frontend — React + TypeScript + Vite

- **Choice:** React + TypeScript built with Vite.
- **Why it fits:** Component model suits a live dashboard; TypeScript keeps socket/REST payloads typed; Vite gives fast dev/build.
- **Alternatives considered:** Vue/Svelte; Next.js (SSR not needed for an internal SPA).
- **Tradeoff / cost:** React app structure and state wiring are the team's responsibility.
- **Status:** planned.

## Map — Leaflet + OpenStreetMap + marker clustering

- **Choice:** Leaflet with OpenStreetMap tiles and marker clustering.
- **Why it fits:** Open-source, no API key, and clustering keeps the map usable with many agents — a core spec requirement.
- **Alternatives considered:** Mapbox/Google Maps (keys, cost, quotas).
- **Tradeoff / cost:** Fewer built-in advanced features than commercial SDKs; clustering tuning needed at scale.
- **Status:** planned.

## Frontend state — TanStack Query + Zustand

- **Choice:** TanStack Query for server/REST state, Zustand for live Socket.IO/operational state.
- **Why it fits:** Clear split — cached server state vs. fast-changing live state — matching the spec's REST-vs-realtime data boundary.
- **Alternatives considered:** Redux (more boilerplate), React Context only (re-render and caching issues).
- **Tradeoff / cost:** Two state tools to learn and keep in their lanes.
- **Status:** planned.

## UI & charts — shadcn/ui + Recharts

- **Choice:** shadcn/ui for components, Recharts for telemetry charts.
- **Why it fits:** shadcn/ui gives accessible, ownable components; Recharts covers live-updating history charts in the detail panel.
- **Alternatives considered:** Material UI / Ant Design (heavier), Chart.js / visx.
- **Tradeoff / cost:** shadcn components are copied into the codebase (owned, not versioned as a dependency).
- **Status:** planned.

## Simulator — Python service over backend REST only

- **Choice:** A separate Python service that registers fake agents and POSTs telemetry through the backend REST API only.
- **Why it fits:** Behaves like external hardware and enforces the "backend is the only gatekeeper" rule — it never touches Postgres or Redis directly.
- **Alternatives considered:** Generating fake data inside the backend (blurs the device boundary), direct DB seeding (bypasses validation).
- **Tradeoff / cost:** One more service to run and configure (agent count, update rate).
- **Status:** planned.

## Infra — Docker + Docker Compose

- **Choice:** Docker + Docker Compose to bring the services up together.
- **Why it fits:** Reproducible, per-project environment; the spec targets `docker compose up`.
- **Alternatives considered:** Locally installed services, Kubernetes (overkill at this stage).
- **Tradeoff / cost:** Requires Docker and port management (we hit and resolved a local Postgres conflict on 5432).
- **Status:** partial — Compose defined and Postgres running; backend, frontend, and simulator services not yet fully wired.

---

## Current Status Summary

- **Implemented:** FastAPI base app, `/health` endpoint, typed settings, `DATABASE_URL`, Docker Postgres, SQLAlchemy async session foundation, Alembic infrastructure, first `Agent` model + migration, Redis connectivity (`REDIS_URL`, async client, `check_redis_connection()`).
- **Planned / not yet implemented:** Redis usage beyond connectivity (latest-state cache, pub/sub, rate limiting, refresh-token store, presence, offline detection), Socket.IO, JWT/RBAC, passlib/bcrypt, frontend (React/Vite/Leaflet/TanStack/Zustand/shadcn/Recharts), simulator behavior, telemetry/alert/command models, alerts, commands.

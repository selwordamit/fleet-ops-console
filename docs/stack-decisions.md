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
- **Status:** implemented. `python-socketio` is mounted as an ASGI wrapper over the FastAPI app. The active event is `agent.telemetry.batch` (one broadcast per 100 ms flush window); the deprecated per-agent `agent.telemetry.updated` is no longer emitted. Connection-status indicator, reconnect resync, and unknown-agent recovery are all implemented on the frontend. Socket is still unauthenticated (dev CORS `*`); auth and Redis pub/sub fan-out are deferred.

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
- **Status:** partial — **Client REST Dashboard MVP implemented and verified**. A Vite + React + TypeScript app under `frontend/` renders `GET /api/agents/current-state`: typed API client (`api/agents.ts`), shared types (`types/agent.ts`), `App.tsx` as data owner (load + loading/error + summary), and a presentational `AgentsTable.tsx`. Served via `npm run dev` (dev proxy `/api` → `http://localhost:8000`); `npm run build` passes. Not yet: routing, WebSocket wiring, frontend Dockerfile.

## Map — Leaflet + OpenStreetMap + marker clustering

- **Choice:** Leaflet with OpenStreetMap tiles and marker clustering.
- **Why it fits:** Open-source, no API key, and clustering keeps the map usable with many agents — a core spec requirement.
- **Alternatives considered:** Mapbox/Google Maps (keys, cost, quotas).
- **Tradeoff / cost:** Fewer built-in advanced features than commercial SDKs; clustering tuning needed at scale.
- **Status:** implemented. `react-leaflet` renders the map on CartoDB Dark Matter tiles. `react-leaflet-cluster` (v2.x, compatible with `react-leaflet@4` / React 18) provides `MarkerClusterGroup` with `disableClusteringAtZoom={18}` and `maxClusterRadius={50}`. Cluster bubbles are restyled to the teal design system via `App.css`. A `MapController` component pans/zooms to the selected agent once per selection change (guarded by `prevSelectedIdRef` to prevent snap-back on telemetry re-renders).

## Frontend state — TanStack Query + Zustand

- **Choice:** TanStack Query for server/REST state, Zustand for live Socket.IO/operational state.
- **Why it fits:** Clear split — cached server state vs. fast-changing live state — matching the spec's REST-vs-realtime data boundary.
- **Alternatives considered:** Redux (more boilerplate), React Context only (re-render and caching issues).
- **Tradeoff / cost:** Two state tools to learn and keep in their lanes.
- **Status:** partially deferred. Neither TanStack Query nor Zustand is installed. Live state is held in `useState` in `App.tsx` (deliberate MVP deviation — will migrate to Zustand when live state spreads beyond `App.tsx`). `@tanstack/react-virtual` is installed and used in `AgentsTable.tsx` for row virtualization — a different TanStack package from TanStack Query.

## UI & charts — shadcn/ui + Recharts

- **Choice:** shadcn/ui for components, Recharts for telemetry charts.
- **Why it fits:** shadcn/ui gives accessible, ownable components; Recharts covers live-updating history charts in the detail panel.
- **Alternatives considered:** Material UI / Ant Design (heavier), Chart.js / visx.
- **Tradeoff / cost:** shadcn components are copied into the codebase (owned, not versioned as a dependency).
- **Status:** planned — neither is installed yet. The Dashboard MVP uses minimal custom CSS (`frontend/src/App.css`, system fonts) instead of a component library, and has no charts.

## Simulator — Python service over backend REST only

- **Choice:** A separate Python service that registers fake agents and POSTs telemetry through the backend REST API only.
- **Why it fits:** Behaves like external hardware and enforces the "backend is the only gatekeeper" rule — it never touches Postgres or Redis directly.
- **Alternatives considered:** Generating fake data inside the backend (blurs the device boundary), direct DB seeding (bypasses validation).
- **Tradeoff / cost:** One more service to run and configure (agent count, update rate).
- **Status:** implemented. Dockerized and wired into Compose. Sends one `POST /api/agents/telemetry/batch` per tick (entire fleet in a single request) via `httpx` async client — replaced the original per-agent sequential loop. A 10 000-agent tick completes in ~0.05 s. Configurable via `AGENT_COUNT`, `TELEMETRY_INTERVAL_SECONDS`, `SIMULATION_MODE`, etc. Not yet implemented: command/ACK behavior; agent reuse/upsert/reset.

## Infra — Docker + Docker Compose

- **Choice:** Docker + Docker Compose to bring the services up together.
- **Why it fits:** Reproducible, per-project environment; the spec targets `docker compose up`.
- **Alternatives considered:** Locally installed services, Kubernetes (overkill at this stage).
- **Tradeoff / cost:** Requires Docker and port management (we hit and resolved a local Postgres conflict on 5432).
- **Status:** implemented. All five services — Postgres, Redis, backend, simulator, frontend — are Dockerized and wired in `docker-compose.yml`. `docker compose up --build` brings up the full stack; health checks gate startup order (backend waits for DB/Redis; simulator and frontend wait for backend `/health`). The backend applies Alembic migrations on startup. Frontend is served on `:5173` with `VITE_PROXY_TARGET` and `VITE_SOCKET_URL` injected via Compose environment.

---

## Current Status Summary

- **Implemented:** FastAPI + Uvicorn, `/health`, typed settings, SQLAlchemy async + Alembic, `Agent` + `Telemetry` models + migrations, telemetry ingestion (per-agent and batch endpoints), `TelemetryBatcher` (100 ms flush, bulk Postgres insert, Redis pipeline, one Socket.IO broadcast), in-memory agent-id cache, Redis latest-state cache + Postgres fallback, Agent API (create/list/get), current-state API, status enum validation, Socket.IO (`python-socketio` ASGI wrapper, `agent.telemetry.batch` event, connection-status UI, reconnect resync, unknown-agent recovery), alerts MVP (low-battery evaluation in batcher flush), simulator (async batch POST via `httpx`, Dockerized, Compose-wired), full five-service Docker Compose stack, frontend (Vite + React + TypeScript, live map with Leaflet + `react-leaflet-cluster`, virtualized table with `@tanstack/react-virtual`, 1-second throttle, `MapController` pan/zoom, CartoDB Dark Matter tiles, teal cluster styling).
- **Partial:** Redis (latest-state writes + reads done; pub/sub fan-out, rate limiting, refresh-token store, presence, offline detection deferred); alerts (evaluation done; persistence table, WebSocket emit, frontend panel deferred).
- **Planned / not yet implemented:** JWT/RBAC + passlib/bcrypt, commands + ACK flow, alert WebSocket events + frontend panel, telemetry history read API + Recharts charts, TanStack Query, Zustand, shadcn/ui, offline detection, multi-worker Redis pub/sub scaling.

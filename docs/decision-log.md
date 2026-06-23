# Decision Log

A running log of significant technical decisions made during implementation.

Use this document to show deliberate engineering thinking. Each entry should explain the decision, alternatives, reason, and tradeoff.

Major stack choices are already described in `docs/onboarding-project-spec.md` and `docs/architecture.md`. This log is for decisions made during the build: folder structure, implementation tradeoffs, temporary shortcuts, fallbacks, and scope decisions.

---

## Entry Template

```md
## YYYY-MM-DD | Short title

Decision: What was decided.

Alternatives: What else was considered.

Reason: Why this choice was made.

Tradeoff: What this choice gives up or postpones.

Verification: How we checked that the decision works in practice.
```

---

## Entries

## 2026-06-07 | Single source of truth: onboarding-project-spec.md

Context: We had confusion between `onboarding-project-spec.md` and `project-spec.md`.

Decision: Keep `onboarding-project-spec.md` as the only authoritative original requirements document and remove `project-spec.md` to avoid ambiguity.

Alternatives: Keep both specs; use `project-spec.md` as a separate working spec.

Reason: One spec avoids contradictions and makes project/Claude reasoning simpler.

Tradeoff: Less separation between original requirements and working interpretation, so implementation notes must live in `architecture.md`, `PROJECT_STATE.md`, and this decision log instead.

Verification: Stale references updated across `CLAUDE.md` and `docs/decision-log.md`; no remaining links to `project-spec.md`.

---

## 2026-06-07 | Docker Postgres for local runtime

Context: We needed a reproducible local PostgreSQL environment.

Decision: Run PostgreSQL through docker-compose using the `fleetops` database/user/password.

Alternatives: Use a locally installed Postgres service.

Reason: Docker gives a predictable, project-specific DB environment.

Tradeoff: Requires Docker running and port management. We hit a local Postgres conflict on port 5432 and resolved it by stopping the local service.

Verification: `docker compose exec postgres psql -U fleetops -d fleetops -c "SELECT 1;"` returned `1`.

---

## 2026-06-07 | SQLAlchemy async with asyncpg

Context: The backend is FastAPI async and needs DB access.

Decision: Use the SQLAlchemy async engine/session with the asyncpg driver.

Alternatives: Use a synchronous SQLAlchemy driver; use raw asyncpg directly.

Reason: SQLAlchemy gives ORM/session structure while asyncpg matches the async backend.

Tradeoff: Async setup is slightly more complex than sync SQLAlchemy.

Verification: `check_db_connection()` returned `True` and `python -m pytest tests/ -q` passed.

---

## 2026-06-07 | Alembic async migration infrastructure

Context: We need reproducible database schema changes before creating business tables.

Decision: Add Alembic configured for async SQLAlchemy.

Alternatives: Create tables manually; delay migrations until later; use a sync migration driver.

Reason: Alembic gives versioned, reviewable schema changes and keeps the DB reproducible.

Tradeoff: The async `env.py` is more complex than the default sync template.

Verification: `python -m alembic history`, `python -m alembic upgrade head --sql`, and `python -m alembic current` completed without errors.

---

## 2026-06-07 | Alembic reads DATABASE_URL from application settings

Context: Alembic needs the DB URL.

Decision: `env.py` reads `settings.database_url` instead of storing the URL in `alembic.ini`.

Alternatives: Put `sqlalchemy.url` directly in `alembic.ini`.

Reason: Keeps one source of truth for DB configuration and avoids credentials in static config.

Tradeoff: Someone reading `alembic.ini` alone will not see the DB URL; they must know `env.py` injects it from settings.

Verification: Alembic commands loaded `env.py` and connected successfully.

---

## 2026-06-07 | First Agent model: integer PK, free-form string status

Context: First real business model (`agents`) needed to prove the model -> metadata -> migration -> table pipeline, without over-engineering fields.

Decision: Use an integer surrogate primary key and a plain `String(20)` `status` (server default `offline`), with `name`, `type`, nullable `last_seen`, and `created_at`/`updated_at` timestamps.

Alternatives: UUID primary key; a database enum or `CheckConstraint` to restrict `status` to idle/en-route/stopped/offline.

Reason: Simplest reasonable first version. Integer PK and a string status keep the first migration readable and easy to evolve; constraints can be added deliberately later.

Tradeoff: No DB-level guarantee of valid `status` values yet; switching the PK type later would require a migration. Validation will live in Pydantic/services for now.

Verification: `alembic revision --autogenerate` detected the table; `alembic upgrade head` applied it; `psql \d agents` shows all 7 columns with `status` defaulting to `offline`; `pytest` confirms `agents` is in `Base.metadata`.

---

## 2026-06-07 | Keep alembic.ini ASCII-only and comments on their own line

Context: Alembic broke completely (`UnicodeDecodeError`, then a bad `script_location`) after documentation comments were added to `alembic.ini`.

Decision: Keep `alembic.ini` ASCII-only and never place inline comments after a value.

Alternatives: Force a UTF-8 read of the ini; leave the rich comments and work around them.

Reason: Alembic reads `alembic.ini` with the OS locale encoding (cp1255 on this Windows machine), which cannot decode non-ASCII bytes such as emoji; and Python's configparser does not strip inline comments, so a trailing `# ...` becomes part of the value (`script_location`).

Tradeoff: Comments in `alembic.ini` must stay plain ASCII and on their own lines, which is slightly less expressive.

Verification: After removing the emoji and moving the inline comment, `alembic current`, `revision --autogenerate`, and `upgrade head` all ran successfully.

---

## 2026-06-07 | Redis client foundation: redis-py asyncio, shared client

Context: The `redis` service existed in docker-compose, but the backend had no Redis client or config yet. We wanted minimal connectivity before building telemetry/cache logic.

Decision: Use the official `redis` package (`redis.asyncio`) with a single shared async client created at import time and `decode_responses=True`, plus a `check_redis_connection()` PING probe — mirroring the shared SQLAlchemy engine pattern in `app/db/session.py`.

Alternatives: Per-request Redis clients; the legacy `aioredis` library; in-memory process state instead of Redis; delaying Redis until telemetry is built.

Reason: redis-py is the official, maintained client and is async-native; a shared client is a simple, consistent foundation that matches the existing DB engine approach. `decode_responses=True` keeps string keys/values ergonomic.

Tradeoff: A module-level client is simple but will need a proper FastAPI startup/shutdown lifecycle (connect/`aclose`) later; `decode_responses=True` is convenient for strings but unsuitable for binary payloads without an override.

Verification: `python -m pytest tests/ -q` passed (12) and a live Redis PING via `check_redis_connection()` returned `True`.

---

## 2026-06-07 | Telemetry ingestion flow: Postgres-first, service-owned transaction

Context: First backend core flow — `POST /api/agents/{agent_id}/telemetry` must persist durable history and update fast latest-state, with thin routes and DB access kept out of handlers.

Decision:

1. Commit telemetry to Postgres **before** writing latest state to Redis.
2. The **service** owns the transaction boundary (calls `commit`); repositories only add/flush and run queries.
3. `recorded_at` is **server-set** for v1 (DB `server_default now()`); no client-supplied timestamp.
4. The **Agent API is deferred**, so agents are seeded manually via SQL for verification.

Alternatives: Redis-first or a single coupled write (risks losing durable data on cache success/DB failure); committing inside repositories (spreads transaction control); requiring a client `recorded_at`; building the Agent API now.

Reason: Postgres is the source of truth, so a Redis hiccup must never roll back a stored report. A service-owned transaction keeps repositories single-purpose and the route thin. Server-set `recorded_at` is the simplest correct default for the MVP. Deferring the Agent API keeps this checkpoint small and focused on the ingestion flow.

Tradeoff: If the Redis write fails after commit, the cache is briefly stale relative to Postgres (acceptable; latest state is reconstructable). Manual SQL seeding is a temporary verification crutch until the Agent API exists. Server-set `recorded_at` can't represent a device reporting an older clock yet.

Verification: `python -m pytest tests/ -q` → 21 passed; `alembic current` → `c258a9ed31eb (head)`; live `POST` returned `201`; `SELECT * FROM telemetry` showed the persisted row; `GET agent:1:state` in Redis showed the latest state; unknown agent → `404`, invalid payload → `422`.

---

## 2026-06-09 | Minimal Agent API: create/list/get only

Context: Telemetry ingestion worked end-to-end, but agents still had to be seeded manually through SQL, which blocked the simulator (and any backend-REST-only client) from registering agents. We needed a way to create and read agents through the backend without expanding scope.

Decision: Add only three endpoints — `POST /api/agents`, `GET /api/agents`, `GET /api/agents/{agent_id}` — reusing the existing `agents` table and `Agent` model (no new migration). Same layering as ingestion: thin route → service (owns the commit) → repository (DB access). No update/delete.

Alternatives: Keep manual SQL seeding; build full Agent CRUD (update/delete, pagination, filtering) now; defer the Agent API until the simulator step and seed via SQL until then.

Reason: Create/list/get is the minimum needed to unblock the simulator's "talks only to the backend over REST" constraint while keeping the checkpoint small and verifiable. Full CRUD and pagination are unproven needs at this stage; manual SQL seeding doesn't satisfy the REST-only rule.

Tradeoff: No update/delete, no pagination on the list endpoint, no auth/RBAC yet (creation is currently open), and `status` remains a free-form string (no enum/constraint). These are deliberate deferrals to later phases.

Verification: Postman `POST /api/agents` → `201` with the persisted agent; `GET /api/agents` → `200` list; `GET /api/agents/{id}` → `200` single agent; `GET /api/agents/{missing_id}` → `404`; `SELECT id, name, type, status FROM agents` confirmed the created agents are persisted in Postgres.

---

## 2026-06-09 | Current-state API: Postgres for identity, Redis for latest state

Context: Telemetry ingestion already wrote each agent's latest state to Redis under `agent:{id}:state`, but there was no backend REST endpoint for clients to read it. The frontend must never read Redis directly — the backend is the gatekeeper.

Decision: Add `GET /api/agents/current-state`, which lists agents from Postgres and, for each, reads its latest state from Redis via a dedicated cache accessor (`read_agent_state`, reusing `agent_state_key`). Agents with no cached state are returned with `latest_state: null`. The Redis read lives in the cache layer; the service orchestrates DB + cache; the route stays thin. The literal route is declared before `/api/agents/{agent_id}` so it is not captured by the int path parameter.

Alternatives: Let the frontend read Redis directly (breaks the gatekeeper rule); reconstruct latest state by querying the newest telemetry row per agent from Postgres (slower, defeats the purpose of the cache); skip agents that have no Redis state (hides registered-but-silent agents); fail the whole request on a cache miss (one silent agent would break the live view).

Reason: The backend stays the single gatekeeper, Redis keeps latest-state reads fast, and registered agents remain visible even before they report telemetry — which is exactly the state operators need to see on the live view.

Tradeoff: The implementation does one Redis `GET` per agent in a sequential loop; for larger fleets this should move to `MGET`/pipelining. No pagination yet. The response also carries both the agent's stored `status` (Postgres) and the last-reported `latest_state.status` (Redis), which can legitimately differ and must not be conflated by consumers.

Verification: `python -m pytest tests/ -q` → 21 passed; route listing confirmed `/api/agents/current-state` is registered before `/api/agents/{agent_id}`; Postman `GET /api/agents/current-state` → `200` returning both a populated `latest_state` (agent with telemetry) and `latest_state: null` (agent without); `redis-cli GET agent:{id}:state` matched the `latest_state` returned by the API.

---

## 2026-06-09 | Status enum validation at the API layer

Context: Before building the simulator (and any other client), we wanted to stop inconsistent status strings — typos, casing, `en_route` vs `en-route` — from entering the system. The allowed values are `idle`, `en-route`, `stopped`, `offline`.

Decision: Add a shared `str`-based Python/Pydantic enum (`AgentStatus`) and use it for `AgentCreate.status` and `TelemetryCreate.status`, with `use_enum_values=True` so the validated value is the plain string. Validation lives at the API boundary only; the SQLAlchemy `String` columns are unchanged.

Alternatives: Keep free-form strings (status quo, no guard); add a PostgreSQL enum type now; add a DB `CheckConstraint` now. The latter two enforce at the database but require a migration and lock the value set into the schema this early.

Reason: A shared API-layer enum prevents inconsistent simulator/client input immediately while keeping the checkpoint small — no migration, no schema change, and the value set stays easy to evolve. The `str` base + `use_enum_values=True` keeps persistence and response serialization as plain strings, so nothing downstream has to know about the enum.

Tradeoff: Enforcement holds only for traffic through the Pydantic schemas — direct SQL or any future non-validated code path could still write an invalid status until a DB-level enum/CheckConstraint is added. Matching is also case-sensitive and exact.

Verification: `python -m pytest tests/ -q` → 42 passed; valid statuses (`idle`, `en-route`, `stopped`, `offline`) accepted on both `POST /api/agents` and telemetry ingestion; invalid statuses (e.g. `moving`, `active`, `EN-ROUTE`) rejected with `422`; `AgentCreate(...).status` confirmed to be a plain `str` (`'en-route'`) after validation.

---

## 2026-06-09 | REST-only configurable simulator with two controlled placement modes

Context: With the Agent API, telemetry ingestion, the current-state API, and status enum validation all proven, we needed a way to generate controlled, realistic-looking data through the backend — to populate the map, exercise ingestion under load, and drive stable demos — without hand-seeding agents.

Decision: Build a standalone Python simulator that talks **only** to the backend REST API (`POST /api/agents`, `POST /api/agents/{id}/telemetry`) and is configured entirely from environment variables. It supports two **controlled** placement modes:

- `local_cluster` — a deterministic spread of `AGENT_COUNT` agents within `SPREAD_RADIUS_KM` of a configurable base point, for clustering/load-style tests.
- `fixed_points` — exact agent locations loaded from a scenario JSON file, for stable, repeatable demos.

Alternatives: Uncontrolled random placement scattered across Israel (unpredictable, hard to demo); hardcoded fixed vehicles only (not scalable to arbitrary counts); generating fake data inside the backend (blurs the device boundary); the simulator writing directly to Postgres/Redis (bypasses validation and breaks the gatekeeper rule).

Reason: Keeping the simulator behind backend REST preserves the "backend is the only gatekeeper" rule and forces the same validation a real device would hit. Two controlled modes make runs predictable: `local_cluster` covers the team-lead requirement to pick an arbitrary agent count (7, 15, 100, 214, eventually 1000) and test clustering/load, while `fixed_points` gives exact, repeatable demo locations. Env-var configuration means behavior changes without code changes.

Tradeoff: Sends are sequential and synchronous (one HTTP request per agent per tick) — simple and easy to reason about, but high counts may need larger intervals or future async/batched sending. Repeated runs create **new** agents because reuse/upsert/reset is not implemented yet, so dev cleanup is manual. Movement is a controlled random walk, not real route/road simulation. No Dockerfile/Compose wiring and no command/ACK support yet.

Verification: `SIMULATION_MODE=local_cluster AGENT_COUNT=3 python -m simulator.app.main` registered 3 agents through the backend API; telemetry persisted as growing rows in Postgres `telemetry`; Redis `agent:{id}:state` keys updated per tick; `GET /api/agents/current-state` returned the simulator agents with populated `latest_state`.

---

## 2026-06-10 | Dockerize backend + simulator; defer frontend behind a Compose profile

Context: Postgres and Redis already ran via Compose, but the backend and simulator were not containerized — the Compose file had placeholder services and a `frontend` service whose `build: ./frontend` would fail because no frontend exists. We wanted backend + simulator to run as containers alongside Postgres/Redis with one command, without building frontend.

Decision:

1. Add `backend/Dockerfile` (`python:3.12-slim`) that installs requirements, copies `app/` + `alembic/`, and on startup runs `alembic upgrade head` then Uvicorn. Migrations run at container start so the schema exists before serving.
2. Add `simulator/Dockerfile` (`python:3.12-slim`) that runs `python -m simulator.app.main`; the package is copied to `/sim/simulator` so the default scenario path still resolves.
3. Wire both into `docker-compose.yml` with in-network hostnames: backend gets `DATABASE_URL=...@postgres:5432/...` and `REDIS_URL=redis://redis:6379/0`; simulator gets `BACKEND_URL=http://backend:8000`.
4. Gate startup with health checks: backend `depends_on` Postgres/Redis `service_healthy`; simulator `depends_on` backend `service_healthy` (backend `/health` returns 200).
5. Move the unbuilt `frontend` service behind a `frontend` Compose **profile** so plain `docker compose up --build` ignores it.

Alternatives considered: comment out / delete the frontend service (loses the documented placeholder); a single combined image for backend+simulator (breaks the device/service boundary — the simulator must look like an external client); `command:`-only migration step instead of baking it into the image CMD (less portable for plain `docker run`); plain `depends_on` without `condition: service_healthy` (start order without readiness, causing early connection/`/health` failures); an external wait-for-it script (extra dependency vs. native health checks).

Reason: Per-service Dockerfiles keep the simulator a separate REST-only client, preserving the "backend is the only gatekeeper" rule. Running migrations on backend startup makes a fresh `docker compose up` self-bootstrapping. Health-check-gated `depends_on` removes race conditions cheaply with no extra scripts. A Compose profile lets the frontend service stay documented and inert until it actually exists — the smallest safe adjustment that keeps `docker compose up --build` working.

Tradeoff: Running `alembic upgrade head` on every backend start is convenient for dev but is not how migrations should be gated in production (should be a controlled deploy step). Health checks add a short startup delay. `python:3.12-slim` differs from the local interpreter (3.13); acceptable since dependencies ship 3.12 wheels. Frontend is intentionally not built, so `docker compose up --build` covers backend + simulator + datastores only.

Verification: `docker compose config --quiet` validated the wiring. Intended end-to-end check: `docker compose up --build` → backend container becomes healthy on `/health`; simulator logs `Registered 3/3 agents` and per-tick `Telemetry tick: 3/3 sent`; `docker compose exec postgres psql ... SELECT count(*) FROM telemetry` grows; `docker compose exec redis redis-cli KEYS "agent:*:state"` lists keys; `GET http://localhost:8000/api/agents/current-state` shows the simulator agents with populated `latest_state`.

---

## 2026-06-10 | Frontend Client REST Dashboard MVP: plain fetch, local CSS, map placeholder

Context: With the backend current-state API proven, the first frontend was built incrementally (Vite shell → types → API client → render → dashboard layout) to display `GET /api/agents/current-state`. The build order's later frontend tooling (TanStack Query, Zustand, Leaflet, shadcn/ui) was explicitly out of scope for this first REST-only screen.

Decision:

1. Scaffold a minimal Vite + React + TypeScript app under `frontend/`, with a single `tsconfig.json` (no project references) and `build` = `tsc --noEmit && vite build` so no stray compiled config artifacts are emitted.
2. Use a Vite dev-server proxy (`/api` → `http://localhost:8000`) so the client calls same-origin relative paths — no CORS setup and no absolute backend URL / env var for the MVP.
3. Fetch with a plain typed client (`api/agents.ts` `getCurrentState()`) called from `App.tsx` via `useEffect`/`useState` — **not** TanStack Query yet.
4. Keep `App.tsx` as the data owner (load + loading/error + derived summary) and `AgentsTable.tsx` as a pure presentational component; types live in `types/agent.ts` mirroring the backend schema (including `agent.status`, which is kept in the model even though the table no longer renders it).
5. Put all styling in `frontend/src/App.css` (imported by `App.tsx`) with system fonts only — **no** large inline `const STYLES` string and **no** external Google Fonts.
6. Render the map area as a labeled placeholder panel; defer Leaflet/OpenStreetMap to a later checkpoint.

Alternatives considered: introduce TanStack Query now (more setup before the wire is even proven; deferred until there is real server-state caching/refetch need); Zustand for the loaded list (unnecessary for a single REST snapshot); absolute backend URL via env var (more config than a dev proxy needs for the MVP); inline `<style>` string or a CSS-in-JS/UI library (rejected — CSS belongs in a stylesheet, kept self-contained); external Google Fonts (adds a third-party network dependency); building the real map now (pulls in Leaflet before the data layer is settled); showing both stored `agent.status` and `latest_state.status` columns (confusing on a REST snapshot — collapsed to one operational `Status` column).

Reason: Each step stayed small and verifiable. A plain `fetch` proves the client→proxy→backend path with the least machinery; TanStack Query/Zustand are deferred until their caching/live-state benefits are actually needed (e.g. when WebSocket arrives). Local CSS with system fonts keeps the project self-contained and the component files focused on structure. A map placeholder reserves the layout slot so the Leaflet checkpoint is a drop-in.

Tradeoff: The manual `useEffect` fetch has no caching, retry, or dedup — and under React `StrictMode` it double-fires in dev (harmless; gone in the production build). There is no refresh/polling, so the screen is a one-shot snapshot until reloaded. The single `Status` column hides the stored `agent.status` (still available in the type for later). No frontend Dockerfile yet; the `frontend` Compose service remains behind a profile.

Verification: `npm run build` (`tsc --noEmit && vite build`) passes; `npm run dev` serves on `:5173`; DevTools Network shows `GET /api/agents/current-state` → 200; the dashboard renders real agents with status badges, agents without a cached snapshot show "No telemetry", the summary counts (total / with / without current state) match, and the map shows the placeholder panel.

---

## 2026-06-11 | WebSocket MVP contract: single `agent.telemetry.updated` event, emit-after-persist

Context: Before writing any Socket.IO code, the project requires the real-time contract to be defined in `docs/ws-protocol.md` so the backend Pydantic event schemas and frontend TypeScript types are built against one fixed wire format. We are in REST snapshot mode; WebSocket is not yet implemented.

Decision: Define an MVP contract with exactly one event, `agent.telemetry.updated` (backend → frontend), wrapped in the project-standard envelope (`type` / `payload` / `ts` / `requestId`). Its payload is `{ agent_id, latest_state }`, where `latest_state` reuses the existing `AgentLatestState` shape from `GET /api/agents/current-state`. The event is emitted **only after** the Postgres telemetry commit **and** the Redis latest-state update both succeed. The frontend loads the initial snapshot via REST, then applies events as live replacements of one agent's `latest_state`. No code was changed in this checkpoint.

Alternatives: Start implementing Socket.IO and let the shape emerge from code (risks backend/frontend drift across two languages); a richer first event carrying full agent metadata (`name`, `type`) per tick (redundant — identity is stable and already loaded from the snapshot); emitting before/independently of the DB+cache writes (could push state a later failure rolls back); pushing full-fleet snapshots over the socket instead of per-agent deltas (defeats the point of an incremental live channel); defining multiple events now (alerts/commands/ACK) before the telemetry channel is even proven.

Reason: Writing the contract first makes the wire format the single fixed point both implementations conform to, per `CLAUDE.md`. Telemetry is the one flow already proven end-to-end, so a single telemetry-push event is the smallest change that turns the refresh-based dashboard live, and reusing `latest_state` means the frontend applies events with zero shape translation. Emit-after-persist extends the existing Postgres-first ingestion rule to the push channel, so events never describe non-durable state and a reconnecting client's REST re-fetch stays consistent.

Tradeoff: A per-agent delta with no metadata means a brand-new agent_id not present in the loaded snapshot is not fully handled yet (deferred). The contract assumes a single backend worker — Redis pub/sub fan-out and multi-worker scaling are out of scope, so this shape will need revisiting before horizontal scaling. No batching/retry/replay, and the socket is unauthenticated in this MVP.

Verification: Documentation-only checkpoint — no runtime behavior to test. Verified the payload matches the live shapes: `backend/app/schemas/agent.py` `AgentLatestState` and `frontend/src/types/agent.ts` `AgentLatestState` (both `lat/lng/speed/battery/status/recorded_at`), and status values match `backend/app/schemas/enums.py` `AgentStatus` (`idle | en-route | stopped | offline`). Envelope matches the `CLAUDE.md` WebSocket Contract Rules.

---

## 2026-06-11 | Backend Socket.IO foundation: wrap FastAPI with socketio.ASGIApp

Context: With the WebSocket contract written, the first runtime step is a minimal Socket.IO server that can accept connections — no telemetry emit yet. It had to coexist with the existing FastAPI REST app without changing any route behavior or the `app.main:app` entrypoint used by Uvicorn, the Dockerfile, and tests.

Decision: Add a dedicated `app/realtime/` package holding `socket.py` (an `socketio.AsyncServer(async_mode="asgi")` plus `connect`/`disconnect` handlers and an optional `connection.ready` envelope emit). In `app/main.py`, keep the FastAPI instance (renamed `api`) with all routers, then export `app = socketio.ASGIApp(sio, other_asgi_app=api)`. Socket.IO owns `/socket.io/*` and the lifespan scope; all other HTTP is forwarded to FastAPI untouched. Added `python-socketio>=5.11.0` to requirements. CORS is opened (`cors_allowed_origins="*"`) for the dev foundation only.

Alternatives: Mount Socket.IO as a sub-app via `api.mount("/socket.io", ...)` (more fragile around the ASGI handshake/lifespan than the wrapper pattern python-socketio documents); run Socket.IO as a separate process/port (extra deployment surface, no benefit at this stage); put the server inline in `main.py` (mixes transport setup with app assembly — a dedicated `realtime/` package keeps the real-time channel's home explicit, parallel to `api/`); use raw Starlette WebSockets instead of Socket.IO (contradicts the chosen stack and the ws-protocol envelope).

Reason: The `ASGIApp(other_asgi_app=...)` wrapper is python-socketio's documented FastAPI integration and the least invasive: REST routing, schemas, and the `app.main:app` import path are all unchanged, so the Dockerfile, Uvicorn command, and existing tests keep working with no edits. A separate `realtime/` package matches the project's layered structure and isolates emit logic for the next checkpoint.

Tradeoff: `cors_allowed_origins="*"` and an unauthenticated socket are acceptable only for this foundation and must be tightened in the socket-auth checkpoint. The module also self-bootstraps logging (`basicConfig` if the root logger is unconfigured) because no central `core/logging` exists yet — a temporary shim to make connect/disconnect visible, to be replaced when real logging config lands. A single-process `AsyncServer` has no cross-worker fan-out; multi-worker scaling (Redis manager) is deferred.

Verification: `python -m pytest tests/ -q` → 42 passed (incl. `test_health` via `TestClient` over the wrapped `app`). `python -c "from app.main import app, api"` → `app` is `ASGIApp`, `api` is `FastAPI`. Ran Uvicorn on the wrapped app and confirmed: `GET /health` → `200 {"status":"ok"}` through the wrapper; a `socketio.AsyncClient` connected (received a `connection.ready` envelope) and disconnected; server logged `Socket.IO client connected/disconnected: sid=...`. No `agent.telemetry.updated` events emitted.

---

## 2026-06-13 | WebSocket telemetry end-to-end: emit-after-persist + frontend live state in existing useState

Context: With the contract (`docs/ws-protocol.md`) and the Socket.IO foundation in place, this arc made `agent.telemetry.updated` real end-to-end — typed event schemas, a dedicated backend emitter, wiring into telemetry ingestion, unit tests, and the frontend consuming events to update the live dashboard. Several layering and scope choices had real alternatives.

Decision:
- Event schemas live in their own module `app/schemas/realtime.py` (`AgentLatestStatePayload`, `AgentTelemetryUpdatedPayload`, `AgentTelemetryUpdatedEvent`), reusing the shared `AgentStatus` enum; `requestId` is snake_case `request_id` internally with a serialization alias, and `ts`/`recorded_at` serialize as ISO-8601 `Z`.
- A dedicated emitter `emit_agent_telemetry_updated(telemetry, request_id=None)` in `app/realtime/socket.py` builds the event from a persisted `Telemetry` row, serializes with `model_dump(mode="json", by_alias=True)`, and broadcasts to all clients, so callers stay transport-agnostic.
- `services/telemetry.py` calls the emitter only after Postgres commit **and** the Redis latest-state write both succeed, wrapped in `try/except` as best-effort: an emit failure logs a warning (with `agent_id`) and still returns the stored row; Postgres/Redis errors are not caught and prevent any emit.
- Frontend: one shared Socket.IO client (`src/realtime/socket.ts`, `autoConnect: false`, backend origin `http://localhost:8000`); `App.tsx` connects in a dedicated `useEffect`, registers named listeners before connecting, and on `agent.telemetry.updated` merges the new `latest_state` into the existing `useState` agents array via an immutable functional update.

Alternatives: reuse the REST `AgentLatestState`/`schemas.telemetry` models for the event (couples the socket wire format to REST/DB shapes — kept separate); emit inside the route or build the envelope dict inline (leaks transport detail into the service — used a dedicated emitter); emit before/independent of persistence, or treat emit failure as ingestion failure (would push state a failure could roll back, or drop durable data over a non-authoritative channel — chose emit-after-persist, best-effort); introduce **Zustand** now for live socket state as `CLAUDE.md` prescribes (deferred — see tradeoff); append unknown `agent_id`s arriving over the socket (out of contract scope — ignored).

Reason: Separate realtime schemas give the cross-language contract one source of truth and prevent REST/DB drift. The emitter keeps Socket.IO concerns in the realtime module so the service just calls one function. Emit-after-persist + best-effort matches the project's Postgres-first rule and keeps the socket a delivery channel, never a gate on data. On the frontend, the dashboard already derives the map/list/summary/detail from one `agents` array, so merging events into that array makes everything update with no new wiring — the smallest correct step.

Tradeoff / cost: Holding live state in `useState` **deviates from the `CLAUDE.md` frontend rule** that Socket.IO state belongs in Zustand. Accepted deliberately for the MVP to avoid introducing a store before it is needed; it will need migrating to Zustand once live state spreads beyond `App.tsx` (or prop-drilling/perf pressure appears). Also deferred: reconnect re-sync (a client that misses events while disconnected is not reconciled), late-registered agents (unknown `agent_id` ignored), connection-status UI, socket auth, and single-worker-only fan-out (no Redis pub/sub).

Impact on the project: The realtime channel is now functional end-to-end — simulator/Postman telemetry appears live on the dashboard (markers move; list/summary/detail update) without refresh. Establishes the emit pattern alerts/commands will reuse, and marks the point where a Zustand migration and socket auth become the next realtime concerns.

Verification: `python -m pytest -q` -> 46 passed (4 new in `tests/test_telemetry_service.py`: emit-once-after-persist with the persisted row, Redis-failure-skips-emit, emit-failure-is-best-effort-and-logs, unknown-agent-no-side-effects). Frontend `npm run build` -> tsc + vite clean. Emitter serialization checked against the contract (status `"en-route"`, `Z` datetimes, `requestId: null`).

---

## 2026-06-13 | WebSocket reconnect recovery: transport reconnect by Socket.IO, state resync by REST snapshot

Context: The live channel delivered `agent.telemetry.updated` events, but a client that briefly lost its connection had no way to recover events emitted while it was offline, and there was no visible connection status. We needed to close that gap without adding a replay/buffer mechanism on the backend. Frontend-only change (`src/App.tsx`, `src/App.css`); no backend, no socket-config, no new features.

Decision: Split recovery into two layers. (1) **Transport reconnect** stays Socket.IO's automatic default — the Manager re-establishes the connection on its own. (2) **State resynchronization** is handled by re-fetching the authoritative REST snapshot. The resync is triggered **only** by the Manager's `reconnect` event (which fires on a successful re-connection and never on the first `connect`), so the initial page-load snapshot is never re-fetched redundantly. On a real reconnect, `getCurrentState()` is called and its result **replaces** the entire local `agents` array (not a merge). If the resync fetch fails, the existing agents state is kept and a clear console error is logged — the app never crashes. A typed `ConnectionStatus` (`connecting | connected | disconnected`) drives a compact header pill (Live / Reconnecting / Disconnected). All listeners, including the two Manager listeners, are removed by named reference on cleanup, so React `StrictMode` cannot accumulate duplicates or fire a duplicate resync.

Alternatives: Replay every missed event from the backend (buffer/sequence-number/since-cursor) — far more backend state and a delivery-guarantee protocol for a problem the authoritative snapshot already solves; trigger resync on every `connect` (would re-fetch redundantly right after the initial snapshot load); **merge** the resync snapshot into local state (can leave stale `latest_state` for agents that changed silently while disconnected — the snapshot is authoritative, so a full replace is correct); track "was previously connected" with a manual ref/flag to distinguish reconnect from first connect (the Manager `reconnect` event already encodes exactly that, with no extra state); add a polling interval as a fallback (rejected — no application-level polling; Socket.IO already reconnects).

Reason: `GET /api/agents/current-state` is already the backend's authoritative current view (Postgres identity + Redis latest state), and the emit-after-persist rule guarantees it is consistent with the last event a client should have seen. Re-reading it on reconnect therefore recovers any missed deltas in one round trip with **zero** new backend machinery — strictly simpler and more robust than replaying individual events. Keying the resync to the Manager `reconnect` event is the precise, StrictMode-safe way to fire it on genuine reconnects only.

Tradeoff: Resync is coarse — it replaces the whole array rather than applying just the missed deltas (fine at this fleet size; could be heavier for very large fleets). There is a brief window during reconnect where the UI shows the pre-outage state until the snapshot returns. Late-registered agents are still not handled (an unknown `agent_id` over the socket is ignored, and a brand-new agent only appears via the next snapshot/resync). The backend socket URL remains hardcoded; socket auth, UI throttling/backpressure, and Redis pub/sub multi-worker fan-out are still deferred.

Impact on the project: The realtime channel is now resilient to transient disconnects and surfaces its own status, closing the WebSocket telemetry phase. The "reconnect -> REST resync replaces state" pattern is the recovery model later realtime channels (alerts, commands/ACKs) can reuse, and it keeps the backend free of replay/buffering responsibilities.

Verification: Frontend `npm run build` (`tsc --noEmit && vite build`) clean; backend `python -m pytest -q` still 46 passed (no runtime code changed). Manual end-to-end with the real backend process: header shows "Live"; stopping the backend flips it to "Disconnected" then "Reconnecting"; restarting it returns to "Live"; on reconnect the dashboard re-fetches `GET /api/agents/current-state`, replaces the agents array, and corrects state with no browser refresh; `LAST SYNC` updates after resync.

---

## 2026-06-16 | Class-based services (AgentService / TelemetryService) with per-request construction

Context: The Agent and Telemetry services were module-level functions that each took `session` (and pulled their collaborators from module imports). We wanted each service to group its related operations and its dependencies in one place, and to make future dependency injection and testing easier — a structural refactor only, no behavior change.

Decision:

1. Convert the function-based services into `AgentService` and `TelemetryService` classes. Each takes the request-scoped `AsyncSession` as the first constructor argument and its collaborators (repository functions, Redis reader/writer, Socket.IO emitter) as keyword arguments that **default to the real implementations**. The class stores these on `self` and its methods use them — not module globals — so the class actually holds the dependencies it uses (not a namespace).
2. Construct one service **per request** via a small FastAPI provider (`get_agent_service` / `get_telemetry_service`) that `Depends(get_db_session)` and returns `Service(session)`. The provider lives in the API layer (route module), so the service layer never imports FastAPI.
3. Keep the transaction boundary in the service (`commit()` + `refresh()` stay in the service methods); repositories still only add/flush/query.
4. Promote the telemetry Redis write from a private module function (`_update_latest_state`) to a module-level `update_latest_state`, so it is injectable as the "Redis latest-state writer" dependency.
5. Rewrite `tests/test_telemetry_service.py` to inject mocks through the constructor (instead of monkeypatching module globals) and add `tests/test_agent_service.py`, both proving constructor injection.

Alternatives considered: keep function-based services (simplest, but dependencies stay implicit module imports and DI/testing relies on monkeypatching global names); introduce full repository **classes** and inject those (more abstraction than this refactor needs — repositories stay as functions per the task's scope limit); build the service once as a global/singleton (rejected — it would capture a request-scoped `AsyncSession`, leaking one request's transaction across requests); put the provider in the service module or a new `deps.py` (kept it in the route module to avoid a new abstraction and keep FastAPI concerns out of `services/`).

Reason: A class groups each domain's operations with the exact dependencies they need and makes the seams explicit, so tests inject fakes through `__init__` rather than patching import names. Per-request construction binds the service to that request's session, preserving correct transaction isolation. Keeping defaults pointing at the real functions means production routes change only from "call function(session, …)" to "Service(session).method(…)" with no wiring boilerplate. Transaction ownership stays in the service for the same Unit-of-Work reason as before: multiple repository calls must be able to commit atomically.

Tradeoff: Slightly more ceremony (a class + a provider) than bare functions for what is still one session per request. The keyword-argument-with-default DI is lightweight rather than a formal container; if the dependency graph grows, a more structured injection approach may be warranted. The `AgentNotFoundError` classes remain defined in both service modules (unchanged) to preserve existing route import paths.

Impact on the project: Establishes the class-based service shape that Alerts and Commands services can follow, and the per-request provider pattern that future services/auth dependencies will reuse. No API behavior, schema, status code, Redis key, WebSocket contract, or logging behavior changed.

Verification: `python -m pytest tests/ -q` → 49 passed (was 46; +3 from new `test_agent_service.py`, telemetry service tests unchanged at 4). App still imports (`from app.main import app, api`); the five `/api` routes and their methods are unchanged, with `/api/agents/current-state` still registered before `/api/agents/{agent_id}`; services do not import FastAPI. Live against the rebuilt backend container: `POST /api/agents` → `201`, `GET /api/agents/{id}` → `200`, missing id → `404`, `POST .../telemetry` → `201` (row persisted in Postgres, `agent:{id}:state` written in Redis), invalid status → `422`, and a Socket.IO client received `agent.telemetry.updated` with the correct payload after a telemetry POST.

---

## 2026-06-16 | Logging & exception-handling policy: layered exceptions, single global 500 handler, centralized logging config

Context: A focused cleanup of logging and exception handling across the existing flows (Agent CRUD, telemetry ingestion, Postgres transactions, Redis reads/writes, Socket.IO). Before the change there was no central handler for unexpected exceptions (an infra failure returned Starlette's plain-text 500), services did not explicitly roll back on a DB write failure, logging config was a `basicConfig` side-effect inside `app/realtime/socket.py`, and the best-effort emit warning lacked event context.

Decision:

1. **One global FastAPI exception handler** (`@api.exception_handler(Exception)` in `app/main.py`) is the single application-level place that logs an unhandled exception's traceback (`logger.exception`) and returns a safe generic `{"detail": "Internal Server Error"}` 500. Internal details are never exposed. The request method + path are logged for context (the path carries the agent id for telemetry) -- no request bodies/secrets.
2. **Layered exception responsibility, no duplicate stack traces.** Repositories do DB access only and let `SQLAlchemyError` propagate. Services own the transaction boundary: on a DB write failure they `rollback()` then re-raise **without logging** (so the global handler logs the single traceback). Routes translate expected domain failures (`AgentNotFoundError`) to HTTP 404 and do not log them again. The only service-level failure log is the best-effort Socket.IO emit warning, which is terminal (not re-raised), so it does not duplicate.
3. **Centralized logging config.** A single guarded `logging.basicConfig` in `app/main.py` (app assembly) replaces the temporary shim in `app/realtime/socket.py`. Every module uses `logging.getLogger(__name__)`. INFO for meaningful success boundaries (agent created -- low frequency), WARNING for degraded-but-successful (best-effort emit failure, now with `event=` + `agent_id=` context), traceback only in the global handler. Telemetry-ingest success is intentionally **not** logged at INFO (high frequency -- one per agent per tick).

Alternatives considered: no global handler (keep Starlette's plain-text 500 and rely solely on uvicorn's traceback -- but the error body is then inconsistent with our JSON `{"detail": ...}` shape and there is no app-owned 500 contract); a `BaseHTTPMiddleware` that catches and suppresses the exception so uvicorn never logs it (more machinery and known middleware caveats -- rejected as over-engineering); logging the DB failure in the service *and* the handler (rejected -- duplicate logs/stack traces for one exception); adding INFO logs to read paths and telemetry ingestion (rejected -- noise; "avoid logging every normal function call"); a third-party structured-logging library (rejected -- not needed for this scope).

Reason: Centralizing the unexpected-exception path gives one safe, consistent 500 response and one application-level traceback, while pushing expected failures to explicit domain exceptions translated at the route keeps each layer single-purpose. Explicit service rollback makes the transaction owner's behavior correct and obvious rather than relying on session teardown. Moving logging config to app assembly removes a module-import side-effect and matches the simulator's `main.py` pattern.

Tradeoff: The global `Exception` handler returns the response but Starlette re-raises internally, so the ASGI server (uvicorn) may also surface the error at its boundary -- we accept that the *application's* single traceback lives in the handler and do not try to suppress the server layer. The telemetry guarantees (Postgres commit -> Redis -> best-effort emit; Redis/Postgres failure skips emit and propagates) are unchanged -- this was a logging/exception cleanup, not a behavior change.

Impact on the project: Establishes the error-handling and logging conventions that Alerts, Commands, and auth will follow (domain exceptions at the service, route translation, one global 500 handler, `getLogger(__name__)`, level discipline). No endpoint paths, schemas, status codes, Redis key format, or WebSocket contract changed.

Verification: `cd backend && python -m pytest -q` -> 53 passed (was 49; +4 from new `test_routes_errors.py`: unknown-agent 404 on both routes, safe-500 with no leaked internals, healthy-list 200). Existing telemetry-service and agent-service tests still pass unchanged in behavior. App imports clean; the `Exception` handler is registered on `api`.

---

## 2026-06-16 | Route-layer structured logging + layered try/except + docstring policy

Context: Building on the logging/exception cleanup, this step added operational observability (structured logs at the HTTP boundary), deliberate per-layer `try/except`, and `"""..."""` docstrings on the public backend surface (handlers, providers, service classes/methods, domain exceptions, realtime emitter). Focused refactor only -- no product features, no contract changes.

Logging responsibilities by layer (the agreed split):

- **Route** -- HTTP boundary. Logs meaningful incoming/successful low-frequency actions at INFO (`agent.create.requested`, `agent.list.completed`, `agent.current_state.completed`) and expected business failures at WARNING (`agent.get.not_found`, `telemetry.ingest.not_found`) with identifiers. It is the single place the not-found condition is logged.
- **Service** -- business flow + transaction. Logs only meaningful outcomes: `agent.created` (INFO) and the terminal best-effort `telemetry_emit_failed` (WARNING). On a DB write failure it rolls back and re-raises **without** logging.
- **Repository/cache** -- data access only; no logging; infrastructure exceptions propagate.
- **Global handler** -- the one place an unhandled exception's traceback is logged (`logger.exception`), returning a safe JSON 500.

All structured logs use a short event-token message plus `extra={"event": ..., "agent_id"/"count": ...}` so a future JSON handler can index them; the payload/request body and the telemetry body are never logged.

Decisions and reasons:

- **Why not broad `try/except Exception` in every route:** only *expected* domain exceptions (`AgentNotFoundError`) are caught and translated to HTTP; everything else must reach the global handler so failures are not silently swallowed and are logged once with a traceback. Broad catches would hide bugs and fragment error handling.
- **Why tracebacks are logged once:** the not-found is logged at the route (no service duplicate); DB failures are rolled back and re-raised unlogged so only the global handler prints the trace; the emit failure is terminal (not re-raised) so its single WARNING+traceback lives in the service. No layer both logs a trace and re-raises.
- **Why telemetry success is not logged at INFO:** ingestion is high-frequency (one per agent per tick, ~N agents every few seconds); a per-event INFO would flood logs and bury signal. Only the expected unknown-agent rejection is logged; unexpected failures rely on service/global logging.
- **Docstring policy:** concise `"""..."""` added to every route handler, the global exception handler, both service providers, both service classes and their public methods, both `AgentNotFoundError` classes, and the realtime connect/disconnect handlers and `emit_agent_telemetry_updated`. Skipped: trivial private helpers (`_envelope`), `__init__` (DI explained on the class), constants. Docstrings state responsibility, side effects, meaningful exceptions, and non-obvious return meaning -- not tutorials, and never repeating the function name.

Alternatives considered: log the not-found in the service as well (rejected -- duplicate log for one condition); add a success INFO to telemetry ingest (rejected -- log flooding); put method/path only in `extra` for the global handler (kept them in the readable message too, since the traceback needs visible context); a JSON logging formatter/library now (deferred -- `extra` fields are already attached; formatting can change later without touching call sites).

Tradeoff: with the current default text formatter the `extra` fields are attached to the record but not printed, so human-readable console output shows the event token without the ids until a structured formatter is added. Accepted: the data is present on the record (and asserted in tests), and adding a JSON formatter later is a config-only change.

Impact: Establishes the route/service/handler logging contract and docstring conventions that Alerts, Commands, and auth will follow. No endpoint paths, schemas, status codes, Redis key format, WebSocket contract, or telemetry ordering changed.

Verification: `cd backend && python -m pytest -q` -> 55 passed (was 53; +2: AgentService DB-failure rollback test, and route INFO-success / telemetry no-INFO tests). Covered: domain exception -> 404 + single structured WARNING; unexpected error -> JSON 500 with no leaked internals; low-frequency success -> INFO; telemetry success -> no INFO from route/service; emit failure -> one WARNING with `event`+`agent_id` and ingestion still 201.

---

## 2026-06-16 | Env-based socket URL + unknown-agent recovery via deduplicated REST resync

Context: Two remaining WebSocket frontend-hardening items. (1) The backend Socket.IO origin was hardcoded in `socket.ts`. (2) An `agent.telemetry.updated` event for an agent not in the loaded snapshot (registered after load) was ignored, so a new agent only appeared on the next reconnect/manual reload. Frontend-only; the WebSocket event payload and backend are unchanged.

Decision:

1. **Env-based socket URL.** `socket.ts` reads `import.meta.env.VITE_SOCKET_URL` and **fails fast** (throws a clear error at load) if it is missing, rather than falling back to an implicit origin. `frontend/.env.example` documents the variable; `vite-env.d.ts` types it; `frontend/.gitignore` ignores `.env`/`.env.local`/`.env.*` while keeping `.env.example`. The REST `/api` Vite proxy is untouched (Socket.IO uses `/socket.io/`, which the proxy does not handle, so the client targets the origin directly).
2. **Unknown-agent recovery.** An event whose `agent_id` is not in the snapshot triggers a re-fetch of `GET /api/agents/current-state` and **replaces** the whole agents array. The event carries no stable identity (`name`/`type`), so the client does **not** synthesize a partial agent. Reconnect resync and unknown-agent recovery share **one** `resyncCurrentState(reason)` function, **deduplicated** by an in-flight `useRef` so concurrent/repeated triggers cause at most one REST request. Known-vs-unknown is decided via an `agentsRef` mirror read **outside** the React state updater (updaters stay pure / StrictMode-safe; no network side effects in them). A failed resync preserves the current agents state and logs the reason including the unknown `agent_id`. Once the snapshot includes the agent, its later events take the normal incremental immutable-replace path.

Alternatives considered: append a partial `Agent` built from `agent_id` + `latest_state` (rejected -- no `name`/`type`, would render a fake/incomplete agent and diverge from the authoritative snapshot); enrich the event payload with full identity so deltas self-describe (rejected -- payload/contract change, out of scope, and identity is stable so re-fetching is simpler); a separate resync path for unknown agents vs reconnect (rejected -- duplicate logic and risk of overlapping requests; one shared deduplicated function is simpler and safer); trigger the fetch inside the `setAgents` updater (rejected -- side effects in updaters double-fire under StrictMode); a hardcoded fallback origin when `VITE_SOCKET_URL` is absent (rejected -- silent wrong-origin connections are hard to diagnose; fail fast instead); keep state-management as-is vs introduce Zustand/TanStack Query (kept as-is -- out of scope, no new library).

Reason: `GET /api/agents/current-state` is already the backend's authoritative view (Postgres identity + Redis latest state), so re-reading it on discovery of an unknown agent recovers full identity in one round trip without a contract change -- the same model already used for reconnect resync, so the two reuse one mechanism. The in-flight ref makes repeated unknown-agent events (which arrive every tick until the snapshot catches up) collapse to a single fetch. Full replacement beats merge because REST is authoritative and a merge could leave stale `latest_state`. Env-based config removes the last hardcoded origin and makes the deployment target explicit, with fail-fast preventing silent misconfiguration.

Tradeoff: discovering a new agent costs a coarse full-fleet `current-state` fetch rather than a targeted per-agent fetch (fine at this fleet size; heavier for very large fleets). There is a brief window between the unknown event and the snapshot returning where the new agent is not yet shown. The fail-fast throw means a missing `VITE_SOCKET_URL` renders a hard error rather than a degraded app -- intentional. In Docker the frontend now requires `VITE_SOCKET_URL` to be provided to the dev server (not changed in this checkpoint; flagged as a follow-up).

Impact on the project: Closes the env-based-socket-URL and unknown-agent items. `VITE_SOCKET_URL` is now external configuration. The shared deduplicated "reconnect / unknown-agent -> authoritative current-state resync" pattern is the recovery model later realtime channels (alerts, commands/ACKs) can reuse. No backend, payload, status-code, Redis-key, or WebSocket-contract change.

Verification: `cd frontend && npm run build` passes; env injection confirmed by building with a sentinel `VITE_SOCKET_URL` (inlined) and fail-fast confirmed by building with it absent (no value inlined -> runtime throw). `cd backend && python -m pytest -q` -> 55 passed, no backend files changed. Live backend check: an agent registered after a snapshot emits `agent.telemetry.updated` and appears in a fresh `current-state` -- the exact data path the resync consumes. Browser manual steps (header Live, live map/table/detail updates, single resync per discovery, StrictMode no-duplicate) documented for human verification.

---

## 2026-06-23 | TelemetryBatcher: decouple HTTP ingest from I/O with an in-process buffer

Context: With 10 000 agents POSTing every 5 seconds the naive flow — one Postgres INSERT + one Redis SET + one Socket.IO emit per HTTP request — could not keep up. Each tick was 10 000 separate round-trips to the DB and Redis.

Decision: Replace the per-request write path with a `TelemetryBatcher` singleton (started/stopped by the FastAPI lifespan). The HTTP handler validates the agent (O(1) set lookup) and appends to an in-memory buffer; a background asyncio task drains the buffer every 100 ms with: one bulk `INSERT` into Postgres (+ alert evaluation) in a single transaction, one Redis pipeline updating all per-agent state keys (last write wins), and one `agent.telemetry.batch` Socket.IO broadcast covering the whole window. Returns a placeholder receipt (id=0) immediately so the HTTP response does not wait for the flush.

Alternatives: Celery/task queue (separate broker service, deployment complexity); asyncio.gather over per-agent DB writes (still N round-trips, just concurrent); Postgres COPY (harder to integrate with SQLAlchemy ORM and alert evaluation).

Reason: An in-process asyncio buffer is the simplest correct solution at single-worker scale: zero new infrastructure, the flush loop runs in the same event loop, and latency between ingestion and persistence is bounded to the flush interval (100 ms by default). The pattern makes the hot path O(1) regardless of fleet size.

Tradeoff: Updates are persisted asynchronously — a process crash within the 100 ms window can lose the buffered tick. Acceptable: telemetry is high-frequency; losing one tick is not an audit failure. The placeholder receipt (id=0) means callers cannot rely on the response for the final DB id.

Verification: `docker compose up --build`; 10 000-agent tick logged at ~0.05 s; Postgres row count growing; Socket.IO broadcast visible in browser DevTools as one `agent.telemetry.batch` event per flush.

---

## 2026-06-23 | Batch telemetry ingest endpoint: skip unknowns rather than 404 the batch

Context: The simulator sends all agents in a single POST. A 404 on any one unknown agent_id would drop the entire tick's data for the fleet.

Decision: `POST /api/agents/telemetry/batch` accepts a JSON array of items. Unknown `agent_id`s are silently skipped (not a 404); known ones are appended to the batcher. Returns `{"accepted": N}` with the count of buffered items.

Alternatives: 404 on first unknown (drops whole batch — unacceptable); 207 multi-status per item (complex response contract for a fire-and-forget path); separate registration check before accept (extra round-trip on hot path).

Reason: A single stale agent_id (e.g. a dev artifact from a previous run) must not silently discard 9 999 valid readings. Skipping and counting is the least-surprise behavior for a bulk ingestion endpoint.

Tradeoff: Unknown agents produce no error visible to the simulator; diagnosing a mis-registered agent requires checking the `accepted` count vs batch size.

Verification: Simulator log shows `agents=10000 sent=10000`; POST with one unknown id returns `{"accepted": 9999}`.

---

## 2026-06-23 | In-memory agent-id cache to eliminate per-request Postgres SELECTs on the hot path

Context: Validating that a telemetry payload's `agent_id` exists before buffering it required a `SELECT` from Postgres on every ingest call. At 10 000 agents × 1 batch per tick this is one round-trip per flush — but in the old per-agent design it was 10 000 round-trips per tick.

Decision: A module-level `_known_agent_ids: set[int]` is populated from Postgres once at application startup (`load_known_agents` called from the FastAPI lifespan). New agents are added to the set when created (`register_known_agent`). Telemetry validation is an O(1) `in` check — no DB round-trip on the hot path.

Alternatives: Redis SET for agent ids (cross-worker safe, but adds a Redis round-trip; unnecessary at single-worker scale); per-request SELECT with connection pooling (still async latency on every ingest); skip validation (allows phantom agent_ids to pollute the telemetry table).

Reason: At single-worker scale an in-process set is the fastest and simplest option. The CLAUDE.md note acknowledges this must move to Redis in a multi-worker deployment.

Tradeoff: The set is process-local — a second Uvicorn worker would have a stale view. Documented as a known single-worker constraint.

Verification: `GET /api/agents/current-state` returns agents; a telemetry POST with an unknown id returns 404 without a DB hit; timing logs show ~0 ms on the validation step.

---

## 2026-06-23 | agent.telemetry.batch replaces per-agent agent.telemetry.updated

Context: The original `agent.telemetry.updated` event was emitted once per telemetry ingestion — one Socket.IO broadcast per agent per tick. With 10 000 agents and a 5-second interval that is 2 000 emits/second, each carrying one agent's state, producing a firehose the browser could not process.

Decision: Deprecate `agent.telemetry.updated`; introduce `agent.telemetry.batch`. The batcher emits one broadcast per flush window covering every agent that reported in that window. The payload is a flat array of `{agent_id, lat, lng, speed, battery, status}`; the envelope `ts` is the recorded time for all items. The deprecated event remains documented in `docs/ws-protocol.md` for historical reference.

Alternatives: Keep per-agent events and rely on frontend throttling alone (still N socket frames per flush, heavy on serialization and transport); SSE (unidirectional, fine, but already committed to Socket.IO); aggregate on the client via a queue (shifts the aggregation burden to every client independently).

Reason: One emit per flush window is fundamentally cheaper than N emits regardless of client-side throttling. The flat array payload avoids nesting (`latest_state: {}`) so the frontend can apply it in a simple loop.

Tradeoff: All items in a batch share the same `ts`; sub-window timing is lost. `requestId` is omitted from the batch envelope (no single correlation id applies to an aggregated batch).

Verification: Browser DevTools shows one `agent.telemetry.batch` event per ~100 ms with a `payload` array of agent updates; `agent.telemetry.updated` is not emitted.

---

## 2026-06-23 | Frontend 1-second state update throttle via pendingUpdatesRef

Context: `onTelemetryBatch` was calling `setAgents()` on every `agent.telemetry.batch` event. With batches arriving every 100 ms and 10 000 agents in state, this triggered a full React re-render 10 times per second — several seconds of browser freeze per update cycle.

Decision: `onTelemetryBatch` writes updates into a `pendingUpdatesRef` (`useRef<Map<number, AgentLatestState>>(new Map())`) instead of calling `setAgents()`. A separate `useEffect` runs a `setInterval` at 1 000 ms; each tick snapshots the pending map, clears it, and calls one `setAgents()`. Latest value per `agent_id` wins within each 1-second window.

Alternatives: `useDeferredValue` / `useTransition` (React concurrent features — still triggers a render per batch, just at lower priority; does not reduce render count); `requestAnimationFrame` accumulator (~16 ms cadence — still 60 re-renders/second); debounce (would delay the update by the full debounce period on every tick, never flushing under continuous load).

Reason: A fixed 1-second flush is the simplest model that directly addresses the root cause (too many `setAgents` calls). It matches the operator's perceptual update rate — a 1-second map refresh is imperceptible in a real fleet context.

Tradeoff: Operators see a position up to ~1 second stale. The snapshot-then-clear ordering before `setAgents` ensures events arriving during the synchronous `.map()` inside the updater land in the next window rather than being lost.

Verification: With 10 000 agents the browser no longer freezes between updates; React DevTools profiler shows one re-render per second.

---

## 2026-06-23 | Virtualized agent table with @tanstack/react-virtual

Context: `AgentsTable` called `agents.map()` and rendered one `<button>` per agent, creating up to 10 000 DOM elements. Every `setAgents()` triggered a commit of all 10 000 nodes — the dominant source of browser parse/layout time.

Decision: Replace `agents.map()` with `useVirtualizer` from `@tanstack/react-virtual`. A scroll container ref is passed to the virtualizer; `getVirtualItems()` returns only the ~25 rows whose pixel range overlaps the current scroll position. Each row is `position: absolute` inside a single spacer `div` of `height: agents.length × 56px`, keeping the scrollbar accurate. `overscan: 5` renders 5 extra rows beyond the visible edge to prevent flashes during fast scrolling.

Alternatives: Windowing with `react-window` or `react-virtualized` (older API, not hooks-based); paginating the table (changes the UX; operators expect a continuous scrollable list); lazy loading (still creates DOM on scroll, does not bound the maximum simultaneously mounted count).

Reason: `@tanstack/react-virtual` is the modern, hooks-based windowing library from the TanStack ecosystem already used in the project (TanStack Query is planned). It integrates cleanly with the existing `<div className="foc-list foc-scroll">` scroll container without restructuring the component.

Tradeoff: Rows are `position: absolute` with an explicit `height: 56px`; if CSS changes make the actual rendered height diverge from the estimate, rows will overlap or leave gaps. The `estimateSize` of 56 px was derived from the actual CSS (`padding: 11px 16px` + two-line text block + `border-bottom: 1px` under `box-sizing: border-box`).

Verification: Chrome DevTools Elements panel shows ~25 `<button>` elements at any scroll position regardless of fleet size; scrolling through 10 000 agents is smooth.

---

## 2026-06-23 | Marker clustering with react-leaflet-cluster; disableClusteringAtZoom=18

Context: With 10 000 agents the Leaflet map rendered 10 000 DOM marker elements at city zoom, causing multi-second parse/layout times on every telemetry update. The spec explicitly calls for marker clustering.

Decision: Wrap all `<Marker>` elements in `<MarkerClusterGroup chunkedLoading disableClusteringAtZoom={18} maxClusterRadius={50}>` from `react-leaflet-cluster` (v2.x, compatible with `react-leaflet@4` / React 18; v4.x requires React 19 and was rejected). `disableClusteringAtZoom={18}` fully unclusters at zoom 18, guaranteeing every individual marker is reachable. `maxClusterRadius={50}` (default 80) tightens clusters at mid-zoom so they expand more gradually. `chunkedLoading` spreads the initial marker registration across animation frames to avoid a first-load freeze.

Alternatives: `leaflet.markercluster` directly without the React wrapper (no lifecycle integration with react-leaflet); `react-leaflet-markercluster` (older, unmaintained); canvas-based rendering (more complex, different visual model); moving to a commercial map SDK (Mapbox GL JS has built-in clustering, but costs money and requires a key).

Reason: `react-leaflet-cluster` is the maintained, React-idiomatic wrapper for Leaflet.markercluster. Installing v2.x (not the latest v4.x) was required because the project uses `react-leaflet@4` which depends on `@react-leaflet/core@2`, not the v3 core that the latest cluster package requires.

Tradeoff: Cluster bubbles use Leaflet.markercluster's default green/yellow/orange styling by default. Overridden in `App.css` with `.marker-cluster-*` rules to match the teal design system. Selected markers inside a cluster are collapsed at zoom < 18; the `MapController` pans to zoom 18 on selection to uncollapse them.

Verification: At zoom 12 the browser renders ~10–20 cluster bubbles instead of 10 000 markers; zooming to 18 expands all clusters; clicking any marker fires `onSelect(agent.id)`.

---

## 2026-06-23 | MapController: pan/zoom to selected agent; prevSelectedIdRef guards re-renders

Context: Selecting an agent from the table had no visible map effect — the agent's marker could be hidden inside a cluster. Operators need the map to navigate to the selected agent automatically. Additionally, telemetry re-renders every ~1 second; without a guard, every re-render would call `setView` and prevent the operator from panning away.

Decision: Add a `MapController` render-null component inside `<MapContainer>` (required so `useMap()` can access the Leaflet instance from React context). It holds a `prevSelectedIdRef` tracking the last `agent_id` it acted on. The `useEffect` fires on every `selectedId` or `located` change but calls `map.setView([lat, lng], 18, { animate: true })` only when `selectedId !== prevSelectedIdRef.current`, then updates the ref. Zoom 18 matches `disableClusteringAtZoom` so the target marker is guaranteed to be unclustered.

Alternatives: A `useEffect` in `App.tsx` using an imperative ref to the map instance (requires threading the map ref through props); calling `setView` on every re-render (causes snap-back on every telemetry tick, preventing free pan/zoom); using `flyTo` instead of `setView` (smoother but longer animation — `setView` with `animate: true` is sufficient).

Reason: The ref guard is the minimal correct solution: it distinguishes a genuine selection change (different id → act) from a telemetry re-render (same id → skip). The `MapController` pattern is idiomatic react-leaflet: components inside `<MapContainer>` access the map instance via context rather than through imperative refs threaded from parent components.

Tradeoff: `MapController` receives the full `located` array on every render to find the selected agent's coordinates; this is a linear scan per selection change (acceptable at 10 000 agents — one scan per selection, not per tick).

Verification: Clicking an agent in the table pans and zooms the map to that agent once; the operator can then freely zoom/pan; selecting a different agent triggers one new pan; re-renders between selections leave the map position unchanged.

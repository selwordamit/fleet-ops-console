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

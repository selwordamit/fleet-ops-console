# Architecture

## Overview

The system has five main containerized services brought up together with Docker Compose:

```text
        ┌─────────────────────────────┐
        │   React + TypeScript SPA    │
        │    map, panels, alerts      │
        └──────────────┬──────────────┘
                       │  HTTP REST + Socket.IO
                       │
        ┌──────────────▼──────────────┐         ┌──────────────────────┐
        │          Backend API        │◀────────│      Simulator        │
        │  FastAPI REST + Socket.IO   │  REST   │   Python service      │
        │  validation, auth, rules,   │  POST   │   fake vehicles       │
        │  persistence, fan-out       │────────▶│   command ACKs        │
        └───────┬──────────────┬───────┘        └──────────────────────┘
                │              │
        ┌───────▼────┐   ┌─────▼─────┐
        │ PostgreSQL │   │   Redis    │
        │ durable DB │   │ cache/pubsub│
        │ history    │   │ ephemeral  │
        └────────────┘   └───────────┘
```

The backend is the single gatekeeper. The simulator talks only to the backend API over REST and never directly to the database or Redis. The backend validates incoming data, persists durable history, updates operational cache, evaluates alert rules, and decides what to push to connected clients.

---

## Service Hierarchy

```text
Presentation layer  →  React SPA in the browser
        │              REST for CRUD/snapshots, Socket.IO for live updates
        ▼
Application layer   →  FastAPI backend, the only gatekeeper
        │              validation, auth, business logic, orchestration
        ▼
Data layer          →  PostgreSQL + Redis
                       PostgreSQL = durable history/audit
                       Redis = fast operational/ephemeral state

Side service        →  Simulator
                       behaves like external hardware/devices
                       speaks only to backend REST APIs
```

Key principle: **nothing bypasses the backend**.

- The simulator does not write to PostgreSQL.
- The simulator does not write to Redis.
- The frontend does not read Redis.
- The frontend does not write to PostgreSQL.
- Every read/write flows through FastAPI, where validation, auth, and business rules are enforced.

---

## Components

### Simulator

Python service that fakes many vehicles. It keeps in-memory state per simulated vehicle and periodically sends telemetry to the backend using the same REST endpoint a real vehicle/device would use.

Responsibilities:
- Generate fake vehicle location, speed, battery, and status.
- Register simulated agents through backend APIs. *(Current implementation registers **new** agents on every run; it does not reuse, upsert, or reset existing agents.)*
- POST telemetry to the backend only.
- Support configurable agent count and update interval for load testing.

Future improvements (not implemented yet):
- Reuse / ensure existing simulated agents instead of creating duplicates on every run.
- Receive forwarded commands from the backend.
- Send command acknowledgements back through the backend.

### Backend API

FastAPI application that owns the business flow.

Responsibilities:
- Validate requests using Pydantic.
- Persist durable data in PostgreSQL.
- Update latest operational state in Redis.
- Evaluate alert rules.
- Publish real-time updates through Socket.IO.
- Manage users, auth, RBAC, agents, alert rules, alerts, commands, and command acknowledgements.

Routes should remain thin. Business logic belongs in services. Database access belongs in repositories.

### Frontend

React + TypeScript SPA.

Responsibilities:
- Fetch initial data snapshots over REST.
- Receive live telemetry, alerts, presence, and command acknowledgements over Socket.IO.
- Render vehicles on a Leaflet + OpenStreetMap map.
- Cluster markers when zoomed out.
- Show vehicle detail panels and telemetry history charts.
- Show non-blocking alert notifications.
- Show command pending/acknowledged/failed states.
- Show connection status and recover gracefully after reconnect.

### PostgreSQL

Durable source of truth for historical and audit data.

Stores:
- users
- agents
- telemetry history
- alert rules
- alerts
- commands

Telemetry is append-heavy and should eventually use native partitioning plus retention. If partitioning becomes a time sink, implement a simple telemetry table first and document partitioning as the intended next step.

### Redis

Fast operational store for state that is either ephemeral or needs fast access.

Used for:
- latest-known-state cache per agent
- Socket.IO pub/sub fan-out when scaling backend workers
- rate limiting
- refresh-token store
- presence
- offline detection source via last-seen/current-state keys

Redis is not the durable source of truth for telemetry history or audit data.

---

## REST API Target Map

All routes are under `/api` except `/health`.

Security note: this is the final secured target state. During early implementation, selected routes may be temporarily unprotected so the backend core can be verified quickly in Postman. JWT and RBAC will be added after the core data flow is proven.

### Health

```text
GET /health
```

### Auth

```text
POST /api/auth/login        — email + password -> access + refresh tokens
POST /api/auth/refresh      — refresh token -> new access token
POST /api/auth/logout       — revoke refresh token
```

### Agents

```text
GET    /api/agents                 — list agents, any authenticated role
GET    /api/agents/{id}            — agent detail, any authenticated role
POST   /api/agents                 — register agent, admin
DELETE /api/agents/{id}            — deregister agent, admin
GET    /api/agents/current-state   — latest state for all visible agents
GET    /api/agents/{id}/history    — telemetry history for charts
POST   /api/agents/{id}/telemetry  — ingest telemetry from simulator/device
```

### Alert Rules

```text
GET    /api/rules          — list rules, any authenticated role
POST   /api/rules          — create rule, operator/admin
PATCH  /api/rules/{id}     — update rule, operator/admin
DELETE /api/rules/{id}     — delete rule, operator/admin
```

### Alerts

```text
GET /api/alerts            — alert list/log, any authenticated role
```

### Commands

```text
POST /api/commands         — issue command, operator/admin
GET  /api/commands         — command history, any authenticated role
POST /api/commands/{id}/ack — simulator callback for command acknowledgement
```

### Users

```text
GET    /api/users
POST   /api/users
PATCH  /api/users/{id}
DELETE /api/users/{id}
```

Admin only in final secured version.

---

## Data Flow — Single Telemetry Update

1. **Simulator → Backend**  
   The simulator sends `POST /api/agents/{id}/telemetry` with GPS, speed, battery, and status.

2. **Backend validates**  
   FastAPI/Pydantic validates the request shape and value ranges.

3. **Backend persists history**  
   Telemetry is inserted into PostgreSQL for history, charts, audit, and later investigation.

4. **Backend updates current state**  
   Redis is updated with the latest state for that agent so the map can load quickly without scanning historical telemetry.

5. **Backend updates agent last_seen**  
   The agent's operational last-seen/status is refreshed.

6. **Backend evaluates alert rules**  
   Rules such as battery below threshold, speed above threshold, or offline are evaluated.

7. **Backend pushes live events**  
   Socket.IO emits `telemetry.updated`. If a rule tripped, it also emits `alert.triggered`.

8. **Client renders**  
   The React app moves the marker, updates the detail panel, and shows alert UI if needed.

---

## Command Flow

1. Operator sends command from the UI.
2. Backend validates role and payload.
3. Backend creates a command row in PostgreSQL with status `pending`.
4. Backend forwards the command to the simulator.
5. Simulator applies or rejects the command.
6. Simulator sends ACK callback to backend.
7. Backend updates command status to `acknowledged`, `failed`, or `expired`.
8. Backend emits command ACK event over Socket.IO.
9. Frontend resolves optimistic pending UI.

Command statuses:

```text
pending | acknowledged | failed | expired
```

---

## Offline Detection

Offline detection cannot rely only on incoming telemetry, because an offline agent stops sending messages.

The system needs an active mechanism:

- A periodic async backend task scans latest `last_seen` values from Redis.
- If an agent has not reported for the configured threshold, for example 60 seconds, it is marked offline.
- The transition emits a live update and may trigger an offline alert rule.

For a single backend worker, a normal asyncio periodic task is enough. For multiple backend workers, the task should use a Redis lock or leader mechanism so only one worker performs the sweep.

---

## Cache vs Database Policy

| Data | PostgreSQL | Redis | Reason |
|---|---:|---:|---|
| Users | Yes | No/optional | Durable auth/account data |
| Agents registry | Yes | Optional | Durable registered devices |
| Telemetry history | Yes | No | Historical investigation and charts |
| Latest telemetry/current state | Optional fallback | Yes | Fast map load and live operational state |
| Alert rules | Yes | Optional cache later | Durable business rules |
| Alerts | Yes | Optional active count | Audit/history |
| Commands | Yes | Optional pending metadata | Audit/history and lifecycle |
| Refresh tokens | No | Yes | TTL and revocation |
| Presence | No | Yes | Ephemeral connection state |
| Rate limits | No | Yes | TTL counters |

---

## Cross-Cutting Concerns

- **Reconnect logic:** Socket.IO handles low-level reconnect; frontend must re-sync state after reconnect.
- **Backpressure/throttling:** high-frequency telemetry should be buffered/coalesced so the UI does not re-render for every single event.
- **Auth on WebSocket:** final system authenticates the Socket.IO connection, not only REST calls.
- **Config via environment:** use typed settings, no hardcoded secrets.
- **Structured logging:** backend logs should make it possible to follow telemetry ingestion, alert triggering, command dispatch, and ACK flow.
- **Seed data:** final demo should provide a first admin/operator user from environment variables or a seed script.

---

## Scaling Notes

Initial version can run with one backend worker.

Scaling path:
- Redis pub/sub enables WebSocket fan-out across multiple backend workers.
- JWT access tokens are stateless, so any worker can validate requests.
- Redis refresh-token store supports logout/revocation across workers.
- Redis rate limiting works across workers.
- Offline sweep needs a single leader/lock when multiple workers exist.


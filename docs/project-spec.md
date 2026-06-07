# Onboarding Project — Real-Time Operations Console

---

## 0. How to read this document

This is the authoritative project specification. It describes what to build and how the pieces should behave.

The project is intentionally large. You are not expected to finish 100% of it. You are expected to make deliberate engineering decisions, build a solid core, and document tradeoffs clearly.

Build the core well before reaching for stretch goals.

---

## 1. Product Overview

### 1.1 What it is

A real-time fleet operations console: a web application where many vehicles continuously report their position and status, and one or more operators watch them live on a map, investigate individual vehicles, receive alerts when something goes wrong, and send commands back.

### 1.2 Domain — Fleet / vehicle tracking

The agents are vehicles in a fleet: trucks, vans, scooters, or delivery vehicles. Each vehicle continuously reports:

- GPS position
- speed
- fuel/battery level
- status: idle, en-route, stopped, offline

Operators watch the fleet live on a map, investigate individual vehicles, receive alerts when something goes wrong, and send commands back to vehicles.

### 1.3 Roles

- **Viewer** — can see the map and device details, read-only.
- **Operator** — everything a viewer can do, plus set alert thresholds and send commands.
- **Admin** — everything an operator can do, plus manage users and device registration.

### 1.4 Core User Stories

1. As a user, I log in and land on a role-appropriate view.
2. As a user, I see all active agents on a live map, updating in near real time without refreshing.
3. As a user, I click an agent and see its live telemetry plus a history chart.
4. As an operator, I define alert rules such as battery below 15%, speed above 90, or offline for more than 60 seconds, and receive real-time alerts when they trip.
5. As an operator, I send a command to a vehicle such as ping, recall to depot, or set status, and see it acknowledged.
6. As a user, when my connection drops, the app tells me and recovers gracefully when it returns.
7. As an admin, I register/deregister agents and manage users.

### 1.5 Key UX Behaviors

- **Live map:** agents appear as markers that move/update as data streams in. With many agents, markers cluster when zoomed out and expand when zoomed in.
- **Detail panel:** clicking a marker opens a side/overlay panel with current values, a small live-updating chart, and operator controls when permitted.
- **Alerts:** when a rule trips, a non-blocking toast/notification appears and the affected marker visibly changes state.
- **Commands:** sending a command shows an optimistic pending state immediately, then resolves to acknowledged or failed when the simulated vehicle responds.
- **Connection awareness:** the UI shows connected, reconnecting, or offline state. On reconnect, state re-syncs automatically.
- **Persistence of preferences:** map position/zoom, selected layers, theme, and unsent command drafts can survive reload without a server round-trip.
- **Presence:** if multiple operators are online, show a simple count or list.

---

## 2. Technical Design

### 2.1 High-Level Architecture

A set of containerized services:

```text
React + TypeScript SPA
        │ HTTP REST + Socket.IO
        ▼
FastAPI Backend API  ◀── REST ── Simulator
        │
        ├── PostgreSQL
        └── Redis
```

The simulator talks only to the backend API over REST and never directly to the database. The backend is the single gatekeeper: it validates, persists, evaluates alert rules, and decides what to push to clients.

All of it should eventually run with Docker Compose.

### 2.2 Data Flow — Single Telemetry Update

1. Simulator sends `POST /api/agents/{id}/telemetry` to the backend.
2. Backend validates the payload.
3. Backend writes telemetry to PostgreSQL as history.
4. Backend updates latest-known-state cache in Redis.
5. Backend evaluates alert rules.
6. Backend pushes telemetry and alert events to clients over Socket.IO.
7. Frontend moves the marker and updates relevant UI.

### 2.3 Commands Flow

1. Operator issues command in UI.
2. Backend validates payload and role.
3. Backend stores command as pending.
4. Backend forwards command to simulator.
5. Simulator applies or rejects command.
6. Simulator sends acknowledgement back through backend.
7. Backend updates command status and pushes ACK to client.
8. Client resolves optimistic pending state.

---

## 3. Chosen Stack

### Frontend

- React + TypeScript
- Vite
- Leaflet + OpenStreetMap + markercluster
- Zustand
- TanStack Query
- shadcn/ui
- Recharts
- socket.io-client

### Backend

- Python
- FastAPI async
- Uvicorn
- Pydantic
- python-socketio

### Database

- PostgreSQL
- Telemetry in a time-series style table, eventually partitioned with retention
- SQLAlchemy async ORM
- Alembic migrations

### Cache / Pub-Sub

- Redis for current-state cache, pub/sub fan-out, rate limiting, refresh-token store, and presence

### Auth

- JWT access + refresh tokens
- RBAC: viewer, operator, admin
- bcrypt via passlib

### Simulator

- Python service
- Talks only to backend REST APIs
- Configurable number of agents and update rate

### Infra

- Docker + Docker Compose
- `.env` based configuration

---

## 4. Suggested Data Model

- **users** — id, email, password_hash, role, timestamps
- **agents** — id, name, type, registration metadata, last_seen, status
- **telemetry** — agent_id, timestamp, lat, lng, speed, battery, status
- **alert_rules** — id, scope, metric, operator, threshold, owner
- **alerts** — id, rule_id, agent_id, triggered_at, resolved_at, value, severity
- **commands** — id, agent_id, issued_by, type, payload, status, timestamps

---

## 5. API and Contract Notes

- REST is used for CRUD, snapshots, auth, users, agents, rules, command history, and command creation.
- Socket.IO/WebSocket is used for live telemetry, alert notifications, command acknowledgements, and presence.
- Define WebSocket message schema before implementation.
- Use a typed envelope such as:

```json
{
  "type": "telemetry.updated",
  "payload": {},
  "ts": "2026-06-06T12:00:00Z"
}
```

- Validate everything coming over the wire on the server. Never trust the client.

---

## 6. Cross-Cutting Concerns

- Reconnect logic on the client.
- Backpressure/throttling for high-frequency telemetry.
- Auth on WebSocket, not only REST.
- Config via environment variables.
- Structured logging.
- Honest scoping and documentation.

---

## 7. Deliverables

1. A running system that comes up with `docker compose up`.
2. Source code for backend, frontend, simulator, and infra.
3. README that includes:
   - how to run it
   - technology decisions and rationale
   - WebSocket message schema
   - what was finished
   - what was deferred
   - what would be improved next
4. Optional but valuable tests:
   - auth
   - alert rule evaluation
   - WebSocket message handling

---

## 8. What Good Looks Like

- The system actually works live.
- Two browser tabs can watch vehicles move in real time.
- Alerts fire in real time.
- Commands show pending state and resolve with acknowledgements.
- Architecture is clean and explainable.
- Redis and PostgreSQL have clearly different responsibilities.
- The map stays usable with many simulated agents.
- Code is typed, readable, and validated.
- Scope is honest.

---

## 9. Stretch Goals

Only after the core works:

- PostGIS/geofencing.
- Heatmap/density layer.
- Advanced alert rule engine.
- Command audit replay.
- Generated TypeScript client from OpenAPI.
- CI.
- Nginx reverse proxy.
- E2E tests.
- Historical playback.
- Multi-tenant organizations.


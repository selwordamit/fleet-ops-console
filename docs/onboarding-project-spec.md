# Onboarding Project — Real-Time Operations Console


---

## 0. How to read this document

This is **not a step-by-step recipe**. It describes *what to build* and *how the pieces should behave*, and it *proposes* a set of technologies — each with a short rationale.

**You are free to swap any major technology** (database, backend framework, cache, real-time transport, map library, etc.) **for an alternative — as long as you write a short paragraph explaining why** your choice is better or equally good for this use case. Minor library choices (state management, component library, chart library, ORM, etc.) are entirely yours and need no justification.

The project is intentionally **large**. You are not expected to finish 100% of it. You *are* expected to work hard, make deliberate engineering decisions, and produce something genuinely good. Anything likely to block you or eat a lot of time is isolated at the end as **non-blocking stretch goals** — do not let those stall the core.

---

## 1. Product overview (PRD)

### 1.1 What it is

A **real-time fleet operations console**: a web application where many **vehicles** in the field continuously report their position and status, and one or more **operators** watch them live on a map, investigate them, get alerted when something goes wrong, and send commands back.

Think of the kind of screen a fleet/operations control center stares at all day — but you are building the whole thing end to end, from the data stream to the pixels.

### 1.2 Domain — Fleet / vehicle tracking

The agents are **vehicles in a fleet** — trucks, vans, scooters, or delivery vehicles. Each vehicle continuously reports its **GPS position, speed, fuel/battery level, and status** (idle / en-route / stopped / offline). Operators watch the fleet live on a map, investigate individual vehicles, get alerted when something goes wrong (low fuel, speeding, gone offline), and send commands back to vehicles.

This domain sets the vocabulary and the specific metrics throughout the rest of this document, but the underlying system design is general.

### 1.3 Who uses it (roles)

- **Viewer** — can see the map and device details, read-only.
- **Operator** — everything a viewer can do, plus set alert thresholds and send commands to agents.
- **Admin** — everything an operator can do, plus manage users and device registration.

### 1.4 Core user stories

1. As a user, I log in and land on a role-appropriate view.
2. As a user, I see all active agents on a live map, updating in (near) real time without refreshing.
3. As a user, I click an agent and see its live telemetry plus a history chart.
4. As an operator, I define alert rules (e.g. "battery < 15%", "speed > 90", "offline > 60s") and receive real-time alerts when they trip.
5. As an operator, I send a command to a vehicle (e.g. "ping", "recall to depot", "set status") and see it acknowledged.
6. As a user, when my connection drops, the app tells me and recovers gracefully when it returns.
7. As an admin, I register/deregister agents and manage users.

### 1.5 Key UX behaviors (how it should *feel*)

- **Live map.** Agents appear as markers that move/update as data streams in. With many agents, markers **cluster** when zoomed out and expand when zoomed in — the map must stay responsive, not freeze.
- **Detail panel.** Clicking a marker opens a side/overlay panel: current values, a small live-updating chart of recent history, and (for operators) controls.
- **Alerts.** When a rule trips, a non-blocking toast/notification appears and the affected marker visibly changes state (color/icon). An alerts list/log is reachable.
- **Commands.** Sending a command shows an **optimistic** "pending" state immediately, then resolves to "acknowledged" or "failed" when the agent (simulated) responds.
- **Connection awareness.** A small, always-visible indicator shows connected / reconnecting / offline. On reconnect, state re-syncs automatically.
- **Persistence of preferences.** Map position/zoom, selected layers, theme, and any draft (e.g. an unsent command) survive a page reload — without a server round-trip.
- **Presence (nice-to-have within core).** If multiple operators are online, show a simple count or list so people know they're not alone in the console.

---

## 2. Technical design

### 2.1 High-level architecture

A set of containerized services that talk to each other:

```
        ┌─────────────────────────────┐
        │   React + TypeScript SPA    │
        │    (map, panels, alerts)    │
        └──────────────┬──────────────┘
                       │  HTTP (REST) + WebSocket
                       │
        ┌──────────────▼──────────────┐         ┌──────────────────────┐
        │          Backend API        │◀────────│    Agent simulator    │
        │   REST + WebSocket server    │  REST   │  (separate service)   │
        │   (validation, auth, alert   │  POST   │  fakes many agents    │
        │    rules, fan-out)           │────────▶│  emitting telemetry   │
        └───────┬──────────────┬───────┘  cmd ACK└──────────────────────┘
                │              │
        ┌───────▼────┐   ┌─────▼─────┐
        │ PostgreSQL │   │   Redis    │
        │ (relational│   │ (cache +   │
        │  + history)│   │  pub/sub)  │
        └────────────┘   └────────────┘
```

**Note:** the simulator talks **only to the backend API** (over REST), never to the database directly. The backend is the single gatekeeper — it validates, persists, evaluates alert rules, and decides what to push to clients. Letting the simulator (or anything) write to Postgres directly would bypass all of that.

All of it is brought up with **Docker Compose** so the whole system starts with one command.

### 2.1.1 Data flow (how a single update travels)

This is the heartbeat of the system — make sure you understand it before building:

1. **Simulator → Server (REST POST).** The simulator loops over its fake agents and, for each, sends an HTTP `POST` to the backend (e.g. `POST /api/agents/{id}/telemetry`) with the new location and metrics.
2. **Server processes it.** The backend validates the payload, writes it to Postgres (history) and updates the latest-known-state cache in Redis, then evaluates the alert rules against the new values.
3. **Server → Clients (WebSocket).** The backend pushes the update out over WebSocket to every connected client (via Redis pub/sub if it runs more than one worker). If a rule tripped, it also pushes an alert event.
4. **Client renders.** The frontend receives the message and moves/updates that agent's marker on the map (and shows a toast if it was an alert).
5. **Commands flow the other way.** An operator issues a command in the UI → it goes to the server (REST or WS) → the server forwards it to the simulator → the simulator applies it to that agent and sends an **acknowledgement** back through the server → the server pushes the ACK to the client, which resolves the optimistic "pending" state.

### 2.2 Proposed technologies (with rationale for major components)

You may replace any **major** component below if you justify it in a short paragraph. **Minor** choices are yours, no justification needed.

#### Frontend — React + TypeScript *(required)*

TypeScript is required for the frontend. Everything else on the client is your call:

- **State / server-state:** your choice (e.g. Zustand, Redux Toolkit, Jotai, or TanStack Query for server state). *Minor — no justification needed.*
- **Component/UI library:** your choice (MUI, Mantine, shadcn/ui, Chakra, or hand-rolled). *Minor.*
- **Charts:** your choice (Recharts, visx, Chart.js, ECharts). *Minor.*

> **Why React + TS:** static typing across a data-heavy, real-time UI catches a whole class of bugs (malformed messages, wrong shapes) at compile time, and the component model fits the panel/marker/alert decomposition cleanly.

#### Backend framework — **Proposed: FastAPI (Python)** *(major — swappable with justification)*

> **Why proposed:** FastAPI is async-native, which suits a server juggling many concurrent WebSocket connections and streaming updates; it gives you typed request/response models (Pydantic) and **auto-generated OpenAPI docs** for free, which keeps the frontend contract honest.
>
> **Acceptable alternatives (justify briefly):** Node.js with Express/Fastify/NestJS (great real-time ecosystem, single language across stack), Go (raw concurrency performance), etc. If you pick one, say why it serves this use case at least as well.

#### Database — **Proposed: PostgreSQL** *(major — swappable with justification)*

> **Why proposed:** You have clearly relational data (users, roles, devices, alert rules, command log) that benefits from constraints, joins, and transactions. Postgres is the sensible default and scales far past what this project needs.
>
> Use a migrations tool (Alembic, Prisma, Drizzle, Flyway — your choice, minor) so the schema is reproducible.

#### Telemetry history storage — *think about this explicitly*

Telemetry is **append-heavy time-series** data (every agent, every few seconds). Naively storing it forever in one wide table will hurt.

> **Options to consider and justify:** (a) a plain partitioned Postgres table with retention, (b) the **TimescaleDB** extension on Postgres for time-series ergonomics, (c) keeping only a rolling window in the DB and the rest in cache. Pick a strategy and explain the trade-off. *(If this becomes a time sink, fall back to a simple table and note it — see stretch goals.)*

#### Cache / pub-sub — **Proposed: Redis** *(major — swappable with justification)*

Redis is proposed to do several jobs. **Explain in the doc which of these you actually used and why:**

- **WebSocket fan-out (pub/sub):** if your backend runs more than one worker/process, an in-memory list of connected clients in one process can't reach clients on another. Redis pub/sub lets any worker publish an update and have every worker push it to its own clients. *This is the canonical "why we need it."*
- **Latest-known-state cache:** keep the most recent telemetry per agent in Redis so the map can paint instantly on load instead of scanning history in Postgres. *Read-heavy, ephemeral — a perfect cache fit.*
- **Rate limiting:** throttle auth attempts and command spam with a Redis counter + TTL.
- **Session / refresh-token store:** track/revoke refresh tokens server-side.

> If you choose a single-process backend and never need fan-out, say so — but then justify how you'd scale, because we want to see you reason about it.

#### Real-time transport — **Proposed: WebSocket** *(major — swappable with justification)*

> **Why we need it:** the whole product is *live*. Agents push updates continuously and operators must see them without polling. Polling thousands of updates per minute is wasteful and laggy; a persistent bidirectional WebSocket channel carries telemetry **down** and commands **up** efficiently.
>
> **Where it's used:** (1) telemetry/position stream to clients, (2) alert notifications, (3) command dispatch + acknowledgements, (4) presence.
>
> **Acceptable alternatives (justify):** Server-Sent Events (simpler, but one-directional — you'd still need something for commands), long-polling (don't). Native WS vs. a library like Socket.IO is a **minor** choice.

#### Map — **Proposed: Leaflet + OpenStreetMap** *(major — swappable with justification)*

> **Why proposed:** Leaflet + OSM tiles are free, lightweight, and need **no API key or paid plan**. That keeps the project self-contained and cheap. Use marker **clustering** to stay performant with many agents.
>
> Heavier geo features (server-side spatial queries, heatmaps, geofencing) are **stretch** — don't start there.

#### Authentication — **Proposed: JWT access + refresh tokens, RBAC** *(major — swappable with justification)*

> **Why proposed:** stateless access tokens are simple for an API + SPA; refresh tokens (stored/revocable, e.g. in Redis) handle session lifetime. Hash passwords with **argon2** or **bcrypt** — never store plaintext. Enforce the three roles (viewer/operator/admin) on every protected endpoint and WS action.
>
> **Acceptable alternative (justify):** server-side sessions with secure cookies.

#### Client-side local storage — **localStorage / IndexedDB** *(minor)*

Persist UI preferences (map view, theme, layers) and drafts (an unsent command) on the client so they survive reload without hitting the server. Use IndexedDB if you want to cache a larger recent-telemetry buffer offline.

#### Agent simulator — **required helper service**

A separate containerized service (your language/choice — Python is a natural fit) that **fakes many agents**. There is no real hardware: this script *is* the agents. It keeps in-memory state for each simulated unit, then on an interval sends updates **to the backend API over REST** (the same `POST .../telemetry` endpoint a real device would use) — never to the database directly. It produces realistic position/telemetry (with some randomness, occasional offline/critical states) and **responds to commands** the server forwards to it by updating that agent's state and sending an acknowledgement back. Without this the system has no life, so treat it as core, not optional. Make the number of agents and the update rate configurable so you can stress the map.

#### Orchestration — **Docker + Docker Compose** *(required)*

One `docker compose up` should bring up: backend API, Postgres, Redis, frontend, and the simulator (plus optional Nginx in stretch). Use a `.env` for config, named volumes for DB persistence, and container healthchecks where it makes sense.

### 2.3 Suggested data model (sketch — refine it yourself)

- **users** — id, email, password_hash, role, timestamps
- **agents/devices** — id, name, type, registration metadata, last_seen, current_state
- **telemetry** — agent_id, timestamp, location (lat/lng), metric values *(time-series — see §2.2 storage note)*
- **alert_rules** — id, scope (agent or global), metric, operator, threshold, owner
- **alerts** — id, rule_id, agent_id, triggered_at, resolved_at, value
- **commands** — id, agent_id, issued_by, type, payload, status (pending/ack/failed), timestamps

### 2.4 Suggested API & contract notes

- REST for CRUD (auth, users, agents, rules, command history) — keep it OpenAPI-documented.
- WebSocket for the live channel — **define your message schema clearly** (a typed envelope like `{ type, payload, ts }`). The frontend TS types and backend models should agree on this shape; documenting it is part of the deliverable.
- Validate everything coming over the wire on the server. Never trust the client.

### 2.5 Cross-cutting concerns to address

- **Reconnect logic** on the client (backoff, re-subscribe, re-sync state).
- **Backpressure / throttling** — if an agent floods updates, the UI shouldn't melt; consider debouncing/coalescing on the server or client.
- **Auth on the WS channel**, not just REST — an unauthenticated socket should get nothing.
- **Config via environment**, no secrets in code.
- **Structured logging** on the backend so you can see what's happening.

---

## 3. Deliverables

1. A running system that comes up with `docker compose up`.
2. Source for: backend, frontend, simulator, and infra (compose, env example).
3. A **README** that includes:
   - How to run it.
   - **Your technology decisions for each major component, with the short rationale** (this is where you justify any swaps).
   - Your WebSocket message schema.
   - What you finished, what you didn't, and what you'd do next.
4. *(Suggested, optional — a plus, not a gate:)* some automated tests — a few meaningful unit/integration tests on the parts that matter most (auth, alert-rule evaluation, WS message handling).

---

## 4. What "really good" looks like

You don't need to finish everything. A strong submission shows:

- **It actually works live** — open two browser tabs, watch agents move and alerts fire in real time.
- **Sensible architecture** — services are separated cleanly, the data flows make sense, and you can explain *why* each major piece is there.
- **Good decisions, well-argued** — your README rationale shows you thought about trade-offs, not just wired things together.
- **It holds up under load** — the map stays usable with a few hundred simulated agents.
- **Clean, typed, readable code** — especially on the TS frontend; clear WS contract; no obvious security holes (hashed passwords, auth enforced, input validated).
- **Honest scoping** — you prioritized the core, and clearly noted what you deferred.

---

## 5. Stretch goals (only after the core works — non-blocking)

These are deliberately last. They are heavier or more likely to cost time; **do not start here**, and don't let them block the core.

- **Server-side spatial features** — PostGIS for geofencing, "agents within radius", proximity queries.
- **Map heatmap / density layer** for many agents.
- **Alert rule engine** with more operators (rate-of-change, sustained-for-N-seconds, compound conditions).
- **Command audit trail** with full history and replay.
- **Generated TypeScript client** from the OpenAPI spec.
- **Basic CI** (lint + tests on push).
- **Nginx reverse proxy** in front of API + frontend in compose.
- **End-to-end tests** (Playwright/Cypress) for the login → map → alert flow.
- **Historical playback** — scrub a time slider and watch past movement replay on the map.
- **Multi-tenant / org separation.**

---

*Build the core well before reaching for stretch. We care more about solid fundamentals and clear reasoning than feature count.*

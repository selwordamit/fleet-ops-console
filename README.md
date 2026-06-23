# Fleet Operations Console

A real-time fleet operations console. Simulated vehicles continuously report telemetry (GPS position, speed, battery, status). Operators watch them live on a map and can select any individual vehicle to inspect its current state.

---

## How to run it

### 1. Create your `.env` file

```bash
cp .env.example .env
```

The file only needs three values — Postgres credentials that Compose uses internally. The defaults in `.env.example` work fine for local development:

```
POSTGRES_USER=fleetops
POSTGRES_PASSWORD=fleetops
POSTGRES_DB=fleetops
```

### 2. Start the full stack

```bash
docker compose up --build
```

Compose brings up five services in dependency order:

| Service | Port | Description |
|---|---|---|
| `postgres` | 5432 | Primary database |
| `redis` | 6379 | Latest-state cache |
| `backend` | 8000 | FastAPI + Socket.IO |
| `simulator` | — | Telemetry generator (no public port) |
| `frontend` | 5173 | React dashboard |

Health checks gate startup: the backend waits for Postgres and Redis to be healthy; the simulator waits for the backend's `/health` endpoint to return 200. On first run the backend applies all Alembic migrations automatically before accepting traffic.

Open **http://localhost:5173** for the dashboard.  
The backend REST + Socket.IO API is at **http://localhost:8000**.

### 3. Configuring agent count and update rate

These are environment variables on the `simulator` service in `docker-compose.yml`:

| Variable | Default | Effect |
|---|---|---|
| `AGENT_COUNT` | `10000` | Number of simulated vehicles to register and stream |
| `TELEMETRY_INTERVAL_SECONDS` | `5` | Seconds between telemetry ticks per agent |
| `SIMULATION_MODE` | `local_cluster` | `local_cluster` (random drift around Tel Aviv) or `fixed_points` (scenario file) |
| `SPREAD_RADIUS_KM` | `2` | Radius in km for `local_cluster` placement |

Override inline without editing the file:

```bash
AGENT_COUNT=500 TELEMETRY_INTERVAL_SECONDS=2 docker compose up --build
```

---

## Technology decisions

### Backend framework — FastAPI (async)

FastAPI was chosen over Django/DRF and Flask because the system is almost entirely I/O-bound: every request either waits on Postgres, Redis, or a Socket.IO emit. A single async Uvicorn worker can handle many concurrent connections without threads. FastAPI also provides Pydantic validation (every incoming telemetry payload is schema-checked) and an OpenAPI spec at `/docs` for free. The tradeoff is that async code must be written carefully — every collaborator in the call chain must be awaited — but for a real-time system this is the right tradeoff.

### Database — PostgreSQL

PostgreSQL is the durable source of truth for all historical telemetry and agent identity. It was chosen over a dedicated time-series database (e.g. TimescaleDB) because the fleet is also relational: agents, commands, alerts, and users are all related entities. Relational integrity and Alembic-versioned migrations were more important at this stage than write throughput. The telemetry table is currently a single append-heavy relation; native partitioning and retention policies are the documented next scalability step.

### Cache and pub-sub — Redis

Redis serves as the operational layer on top of Postgres. The roles actually implemented are: (1) **latest-state cache** — after each flush the backend writes every agent's last known position, speed, battery, and status to `agent:{id}:state` as a JSON string, so `GET /api/agents/current-state` reads from Redis rather than scanning telemetry history; (2) **write pipeline** — the batcher uses a Redis pipeline to batch all per-agent state updates into a single round trip per flush. Planned but not yet implemented: pub/sub fan-out for multi-worker scaling, refresh-token storage, rate limiting, and offline-detection presence keys. The design keeps Redis ephemeral and Postgres authoritative: a cold Redis is always safe to rebuild from the telemetry table.

### Real-time transport — Socket.IO over WebSocket

The spec calls for live operator updates and reconnect awareness. Socket.IO was chosen over raw WebSockets because it provides automatic reconnection with exponential backoff, a named event model, and a matching browser client (`socket.io-client`) that removes all the hand-rolled multiplexing that raw WebSocket would require. The backend uses `python-socketio` mounted as an ASGI middleware on top of the FastAPI app — both REST and Socket.IO traffic are served from the same port 8000 without a separate process. The cost is that both ends must agree on the message envelope; that contract is defined in `docs/ws-protocol.md` and reflected in both the backend Pydantic schemas and the frontend TypeScript types.

### Map — Leaflet + OpenStreetMap + react-leaflet-cluster

Leaflet with OpenStreetMap tiles was chosen over Mapbox or Google Maps because it is fully open-source and requires no API key or account. `react-leaflet` provides the React component bindings. `react-leaflet-cluster` (v2, compatible with react-leaflet v4 / React 18) wraps Leaflet.markercluster and collapses nearby markers into cluster bubbles at low zoom, which is essential for 10,000 agents on a single map. Clustering is disabled at zoom 18 (`disableClusteringAtZoom={18}`) so individual markers are always reachable by zooming in. Selecting an agent from the table triggers `map.setView([lat, lng], 18)` via the `MapController` component (which uses `useMap()` from inside `<MapContainer>`), panning and zooming to the agent once; a ref guard prevents subsequent telemetry re-renders from snapping the view back.

### Simulator — Python service over backend REST

The simulator is a standalone Python service that registers fake agents and POSTs telemetry through the backend REST API. It never touches Postgres or Redis directly. This enforces the "backend is the only gatekeeper" rule: validation, persistence, and fan-out are all backend responsibilities regardless of whether the source is real hardware or simulation. The simulator is configurable via environment variables and is Dockerized so `docker compose up` starts it automatically. The tick implementation sends a single batch POST for the entire fleet per interval, not one request per agent — see the performance section below.

### Orchestration — Docker Compose

Docker Compose brings the entire five-service stack up with a single command and a single `.env` file. It was chosen over locally installed services because it gives a fully reproducible environment with no host dependencies beyond Docker. Postgres and Redis use official Alpine images; the backend and simulator are built from their own Dockerfiles. Health checks with `depends_on: condition: service_healthy` guarantee Postgres and Redis are accepting connections before the backend starts, and that the backend is serving HTTP before the simulator registers agents.

---

## WebSocket message schema

Full contract: [`docs/ws-protocol.md`](docs/ws-protocol.md).

### Envelope

Every event uses the same envelope:

```json
{
  "type": "agent.telemetry.batch",
  "payload": [ ... ],
  "ts": "2026-06-22T09:15:03Z"
}
```

| Field | Type | Description |
|---|---|---|
| `type` | string | Event name |
| `payload` | object or array | Event-specific data |
| `ts` | ISO 8601 UTC string | When the backend emitted the event; used as `recorded_at` for all items in a batch |
| `requestId` | string (optional) | Correlation id, omitted on batch events |

### Active event: `agent.telemetry.batch`

Direction: **backend → all connected clients**. Emitted once per batcher flush window (every 100 ms by default), covering every agent that reported in that window.

```json
{
  "type": "agent.telemetry.batch",
  "payload": [
    {
      "agent_id": 1,
      "lat": 32.0853,
      "lng": 34.7818,
      "speed": 42.5,
      "battery": 87.0,
      "status": "en-route"
    },
    {
      "agent_id": 2,
      "lat": 32.0901,
      "lng": 34.7720,
      "speed": 0.0,
      "battery": 64.0,
      "status": "idle"
    }
  ],
  "ts": "2026-06-22T09:15:03Z"
}
```

`status` is one of `idle | en-route | stopped | offline`. Each item carries no `recorded_at`; the frontend uses the envelope `ts` for all items in the batch. If an agent reported more than once in the flush window, only its last reading appears (last write wins).

Backend source: `backend/app/services/telemetry.py` → `TelemetryBatcher._flush`.  
Frontend types: `frontend/src/types/socket.ts` → `AgentTelemetryBatchEvent`.

### Deprecated event: `agent.telemetry.updated`

The original per-agent event (one Socket.IO emit per telemetry ingestion) is documented in `docs/ws-protocol.md` for historical reference. It is no longer emitted. The batch event replaced it to keep the channel flat under high agent counts.

### Frontend consumption model

1. **Initial snapshot:** the dashboard calls `GET /api/agents/current-state` over REST on mount. This loads every agent's identity (`name`, `type`) and latest state in one response.
2. **Live updates:** the Socket.IO client then applies each `agent.telemetry.batch` event by replacing the matching `latest_state` for each `agent_id` in the existing array.
3. **Unknown agents:** if a batch item references an `agent_id` not in the current snapshot (e.g. an agent registered after the dashboard loaded), the frontend triggers a single deduplicated re-fetch of the full snapshot.

---

## What is finished, what is deferred, and what comes next

### Finished

- **Telemetry pipeline:** simulator → batch REST endpoint → `TelemetryBatcher` → bulk Postgres insert + Redis pipeline + one Socket.IO broadcast per flush window.
- **Live map:** Leaflet + OpenStreetMap tiles, `react-leaflet-cluster` for marker clustering, per-status colored markers, click-to-select with map pan/zoom, cluster styling matching the design system.
- **Virtualized agent table:** `@tanstack/react-virtual` renders only the ~20–25 visible rows out of 10,000 (constant DOM size).
- **Performance work for 10,000 agents:** see performance section below.
- **Docker Compose full stack:** all five services with health checks and ordered startup.
- **REST API:** `POST /api/agents`, `GET /api/agents`, `GET /api/agents/current-state`, `POST /api/agents/{id}/telemetry`, `POST /api/agents/telemetry/batch`.

### Deferred

- **Alerts:** the spec defines low-battery and offline alert rules, evaluation, persistence, and WebSocket alert events. The `AlertService` stub exists in the backend but alert events are not emitted to clients yet.
- **Operator commands:** command creation (`POST /api/agents/{id}/commands`), pending-state UI, simulator acknowledgement, and the `command.ack` WebSocket event.
- **JWT + RBAC:** access and refresh tokens, bcrypt password hashing, role-based route and socket guards. The backend is intentionally unauthenticated at this stage so the core flow can be verified without auth complexity.
- **Telemetry history charts:** the spec's agent detail panel includes a Recharts battery/speed timeline. The detail panel exists but shows only the current-state snapshot.
- **Rate limiting, offline sweep, and retention:** Redis-based per-agent rate limiting, a background sweep that marks agents offline when they stop reporting, and Postgres telemetry retention/partitioning.

### What I would do next

Auth first (JWT + bcrypt makes the app minimally deployable), then the alert pipeline (evaluation already runs in the batcher — just needs the Socket.IO emit and frontend handling), then commands. Retention and partitioning become necessary once the telemetry table grows past tens of millions of rows.

---

## Performance

The spec targets 10,000 agents reporting continuously. Several layers of optimization were added to hit this at a responsive frame rate:

**Simulator — single batch POST per tick.**  
The original design sent one HTTP request per agent per tick (10,000 concurrent requests). The simulator was rewritten to build the full tick payload in memory and send it as a single `POST /api/agents/telemetry/batch`. A 10,000-agent tick completes in approximately 0.05 s.

**Backend — `TelemetryBatcher` (100 ms flush loop).**  
The `POST /api/agents/{id}/telemetry` and batch endpoints append to an in-memory buffer and return immediately (O(1)). A background asyncio task drains the buffer every 100 ms with: one bulk `INSERT` into Postgres, one Redis pipeline updating all per-agent state keys (last write wins), and one Socket.IO `emit` broadcasting the entire window to all clients. This keeps every expensive I/O operation flat — constant per flush regardless of fleet size — instead of one DB round-trip per agent per tick.

**Backend — in-memory agent ID cache.**  
The 404 guard on the telemetry hot path is an O(1) Python set lookup against `_known_agent_ids`, populated at startup from Postgres. Unknown agents are rejected immediately without a database round-trip.

**Frontend — 1-second state update throttle.**  
The Socket.IO batch event can arrive up to 10 times per second (the batcher flushes every 100 ms). Calling `setAgents()` on every event triggered a full React re-render 10 times per second over 10,000 agents — several seconds of browser freeze per update. The `onTelemetryBatch` handler now writes updates into a `pendingUpdatesRef` (a `Map<agentId, latestState>`), and a separate `setInterval` flushes all accumulated updates into React state in a single `setAgents()` call once per second. Source: `frontend/src/App.tsx`.

**Frontend — virtualized agent table.**  
`AgentsTable` previously called `agents.map()` and rendered one `<button>` per agent, creating up to 10,000 DOM elements. `@tanstack/react-virtual` replaces this with a scroll container that renders only the ~20–25 rows visible in the viewport at any moment. A spacer div of `agents.length × 56 px` keeps the scrollbar accurate. Source: `frontend/src/features/agents/AgentsTable.tsx`.

**Frontend — marker clustering.**  
`react-leaflet-cluster` (wrapping Leaflet.markercluster) groups geographically close markers into cluster bubbles at low zoom. At city view (zoom 12), 10,000 markers collapse to a handful of cluster circles — the browser renders tens of DOM elements, not thousands. Clustering disables at zoom 18 so individual markers are always reachable. Source: `frontend/src/features/map/FleetMap.tsx`.

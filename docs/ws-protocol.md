# WebSocket Protocol Contract

The real-time event contract for the Fleet Operations Console. This document is
written **before** any Socket.IO code so the backend Pydantic event schemas and
the frontend TypeScript types both conform to one wire format.

> **Status:** Post-MVP. The active telemetry event is now
> [`agent.telemetry.batch`](#event-agenttelemetrybatch) — a single broadcast per
> flush window introduced by the backend batching refactor. The original
> per-agent [`agent.telemetry.updated`](#event-agenttelemetryupdated-deprecated)
> event is **deprecated** and no longer emitted. Everything else is explicitly
> out of scope (see [Out of scope](#out-of-scope)).

> **Source of truth note:** Postgres remains the source of truth for telemetry
> history. Redis remains the latest/current-state cache. The backend remains the
> only gatekeeper — clients never read Postgres or Redis directly.

---

## Transport

- **Channel:** Socket.IO over WebSocket (the project's chosen real-time stack).
- **Encoding:** JSON.
- **MVP authentication:** none yet. The socket connection is unauthenticated in
  this checkpoint. Auth/RBAC on the socket is deferred (see
  [Out of scope](#out-of-scope)).

---

## Envelope

Every event uses the project-standard envelope (see `CLAUDE.md` → *WebSocket
Contract Rules*). The event name goes in `type`; the event-specific data goes in
`payload`.

```json
{
  "type": "agent.telemetry.updated",
  "payload": {},
  "ts": "2026-06-06T12:00:00Z",
  "requestId": "optional-correlation-id"
}
```

| Field       | Type            | Required | Meaning                                                            |
| ----------- | --------------- | -------- | ------------------------------------------------------------------ |
| `type`      | string          | yes      | Event name. For this contract, always `agent.telemetry.updated`.   |
| `payload`   | object          | yes      | Event-specific data. Shape defined per event below.                |
| `ts`        | string (ISO8601 UTC) | yes | When the backend emitted the event.                                |
| `requestId` | string          | no       | Optional correlation id for tracing a single ingestion end-to-end. |

---

## Event: `agent.telemetry.updated` (deprecated)

> **Deprecated — no longer emitted.** Superseded by
> [`agent.telemetry.batch`](#event-agenttelemetrybatch). The backend batching
> refactor replaced this per-agent event with a single batched broadcast per
> flush window. This section is retained for historical reference; the contract
> below describes the old wire format and should **not** be relied on by clients.

### Direction

**Backend → Frontend.** The backend emits this event to connected clients. The
frontend only listens; it never sends this event.

### Purpose

Notify connected operators that a single agent has reported new telemetry, so the
map, list, and detail views update live without a manual refresh. The frontend
treats this as a **live replacement for one agent's `latest_state`**.

### Flow

```text
Simulator
  -> POST /api/agents/{agent_id}/telemetry
  -> Backend validates payload
  -> Backend saves telemetry to Postgres (insert + commit)
  -> Backend updates Redis latest-state cache (agent:{id}:state)
  -> Backend emits agent.telemetry.updated   <-- this event
  -> Frontend updates map / list / detail without manual refresh
```

### Emit timing

The backend emits the event **only after both** of the following have succeeded,
in this order:

1. **Postgres** telemetry insert/commit succeeds.
2. **Redis** latest-state update succeeds.

This mirrors the existing Postgres-first ingestion rule: the event must never
describe state that a later failure could roll back. Because the event is emitted
only after durable + cache writes succeed, a client that reconnects and re-fetches
`GET /api/agents/current-state` will see state consistent with the last event it
received.

If either write fails, the event is **not** emitted for that tick.

### Payload shape

```ts
{
  agent_id: number;
  latest_state: {
    lat: number;
    lng: number;
    speed: number;
    battery: number;
    status: "idle" | "en-route" | "stopped" | "offline";
    recorded_at: string; // ISO 8601 datetime
  };
}
```

This `latest_state` shape is **identical** to `AgentLatestState` returned by
`GET /api/agents/current-state`, so the frontend can apply it directly:

- Backend: `backend/app/schemas/agent.py` → `AgentLatestState`.
- Frontend: `frontend/src/types/agent.ts` → `AgentLatestState`.
- Status values: `backend/app/schemas/enums.py` → `AgentStatus`
  (`idle | en-route | stopped | offline`).

### Example

```json
{
  "type": "agent.telemetry.updated",
  "payload": {
    "agent_id": 1,
    "latest_state": {
      "lat": 32.0853,
      "lng": 34.7818,
      "speed": 42.5,
      "battery": 87.0,
      "status": "en-route",
      "recorded_at": "2026-06-11T09:15:03Z"
    }
  },
  "ts": "2026-06-11T09:15:03Z",
  "requestId": "ingest-1-1749632103"
}
```

### Field notes

- The payload carries **only** `agent_id` and `latest_state`. It intentionally
  **omits** full agent metadata such as `name` and `type` — those are stable
  identity fields the frontend already has from the initial snapshot and that do
  not change per telemetry tick. They can be added later if a concrete need
  arises.
- `agent_id` is the integer agent id (same value as `id` in
  `GET /api/agents/current-state`). The frontend uses it to locate which agent's
  `latest_state` to replace.

---

## Event: `agent.telemetry.batch`

### Direction

**Backend → Frontend.** The backend emits this event to connected clients. The
frontend only listens; it never sends this event.

### Purpose

Notify connected operators that one or more agents have reported new telemetry,
so the map, list, and detail views update live without a manual refresh. This is
the **active** telemetry event, replacing the deprecated per-agent
`agent.telemetry.updated`.

### Why batched

The backend buffers incoming telemetry and drains it on a fixed interval (the
`TelemetryBatcher` flush loop). Each flush performs one bulk Postgres insert, one
Redis pipeline, and **one** Socket.IO broadcast covering every agent that
reported in that window — regardless of fleet size. This keeps the real-time
channel flat under hundreds/thousands of agents instead of emitting one event per
agent per tick.

### Flow

```text
Simulator
  -> POST /api/agents/{agent_id}/telemetry   (many agents, concurrently)
  -> Backend validates payload, appends to the batch buffer
  -> Batcher flush loop (every flush_interval):
       -> bulk INSERT to Postgres (+ alert evaluation) in one transaction
       -> Redis pipeline updates each agent's latest state (last write wins)
       -> emits ONE agent.telemetry.batch covering the whole window  <-- this event
  -> Frontend applies every item in the batch to map / list / detail
```

### Emit timing

The batch is emitted **after** the flush's Postgres transaction commits. The
Redis pipeline and the emit are best-effort within the same flush: a Redis or
emit failure is logged and does not roll back the durable insert. If the Postgres
transaction fails, the batch is rolled back and **not** emitted for that window.

### Payload shape

`payload` is an **array** of flat per-agent items (note: no nested
`latest_state`, and **no `recorded_at`** — the envelope `ts` is the recorded time
for every item in the window):

```ts
{
  agent_id: number;
  lat: number;
  lng: number;
  speed: number;
  battery: number;
  status: "idle" | "en-route" | "stopped" | "offline";
}[]
```

- Backend producer: `backend/app/services/telemetry.py` → `TelemetryBatcher._flush`
  (event name constant `TELEMETRY_BATCH_EVENT = "agent.telemetry.batch"`).
- Frontend types: `frontend/src/types/socket.ts` →
  `AgentTelemetryBatchEvent` / `AgentTelemetryBatchItem`.
- Status values: `backend/app/schemas/enums.py` → `AgentStatus`
  (`idle | en-route | stopped | offline`).

If an agent reports more than once within a single flush window, only its **last**
reading appears in the batch (last write wins for current state).

### Example

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

### Field notes

- The envelope omits `requestId`: a batch aggregates many ingestions, so no single
  correlation id applies.
- Each item omits `recorded_at`; the frontend uses the envelope `ts` as the
  recorded time for every item in that batch.
- Items omit agent metadata (`name`, `type`) for the same reason as the deprecated
  event: those are stable identity fields the frontend already holds from the
  initial snapshot.

---

## Frontend consumption model

1. **Initial load (snapshot):** the dashboard loads the full fleet via
   `GET /api/agents/current-state` (REST). This is the source for the initial
   render, including agent identity (`name`, `type`) and any agents that have not
   reported telemetry yet (`latest_state: null`).
2. **Live updates:** the frontend then applies each `agent.telemetry.batch`
   event by iterating its `payload` array and replacing each matching agent's
   `latest_state` in place, using the envelope `ts` as `recorded_at`.

REST remains the way the dashboard snapshot is loaded; the WebSocket event is the
way that snapshot is kept live afterward.

Handling a batch item for an `agent_id` **not** present in the current snapshot
(e.g. an agent registered after load) is supported: because the item carries no
stable identity (`name`/`type`), the client does **not** construct a partial
agent. Instead the first such unknown item in a batch triggers a single,
deduplicated re-fetch of `GET /api/agents/current-state` and replaces the whole
agents array; subsequent batches for that now-known agent take the normal
incremental path. The payload is unchanged — this is purely client recovery
behavior.

---

## Out of scope

This document and checkpoint deliberately exclude:

- Commands and command creation.
- ACK handling.
- Alerts and alert events.
- Auth/RBAC on the socket connection.
- Presence.
- Rooms.
- Redis pub/sub fan-out.
- Multi-worker scaling.
- Retry / replay.
- Telemetry history streaming.
- Marker clustering.
- Frontend implementation.
- Backend Socket.IO implementation.

These will be defined in later versions of this protocol document as their
checkpoints are reached.

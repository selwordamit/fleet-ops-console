# WebSocket Telemetry MVP

Teaching-oriented summary of the real-time telemetry phase (build-order step 5).

## Goal

Keep the operator dashboard live: when an agent reports new telemetry, the map,
list, and detail panel update **without a manual refresh**. The backend stays the
only gatekeeper — the frontend never reads Postgres or Redis directly.

## High-level flow

```
Simulator / Postman
  → POST /api/agents/{id}/telemetry        (REST ingestion)
  → FastAPI route + Pydantic validation
  → telemetry service (ingest_telemetry)
  → PostgreSQL  (insert + commit — source of truth)
  → Redis       (agent:{id}:state — current-state cache)
  → Socket.IO   (emit agent.telemetry.updated — broadcast)
  → React socket listener (onTelemetryUpdated)
  → React state (setAgents — immutable replace)
  → live UI (map markers / list / details re-render)
```

A separate one-time `GET /api/agents/current-state` (REST) loads the initial
snapshot; Socket.IO events keep it live afterward. After a dropped connection,
Socket.IO reconnects the transport automatically and the frontend re-fetches that
same snapshot to resynchronize (see *Connection status & reconnect resync*).

## Relevant files

**Backend**

- `backend/app/main.py` — wraps FastAPI and the Socket.IO server into one ASGI app on a single port.
- `backend/app/realtime/socket.py` — creates the `AsyncServer`, handles connect/disconnect, and broadcasts `agent.telemetry.updated`.
- `backend/app/realtime/__init__.py` — marks the realtime package as the channel's home, separate from REST.
- `backend/app/schemas/realtime.py` — Pydantic event/payload schemas with the `requestId` alias and ISO-UTC serialization.
- `backend/app/services/telemetry.py` — orchestrates validate → persist → cache → emit and applies the best-effort emit policy.
- `backend/app/api/routes/telemetry.py` — thin REST route that receives telemetry and delegates to the service.
- `backend/app/repositories/telemetry.py` / `agent.py` — database-only insert and agent-existence lookup.
- `backend/app/cache/agent_state.py`, `client.py`, `keys.py` — Redis client, `agent:{id}:state` key, and read/write of latest state.
- `backend/app/schemas/agent.py` / `services/agent.py` — build the REST current-state snapshot sharing the `AgentLatestState` shape.

**Frontend**

- `frontend/src/realtime/socket.ts` — single shared socket.io-client instance with `autoConnect: false`.
- `frontend/src/types/socket.ts` / `types/agent.ts` — event types that reuse the same `AgentLatestState` shape as the snapshot.
- `frontend/src/App.tsx` — loads the snapshot, registers listeners before connecting, applies each event to React state, drives the connection-status indicator, and runs the REST resync on reconnect.
- `frontend/src/App.css` — dashboard styling, including the `.foc-conn` connection-status pill in the header.
- `frontend/src/features/map/FleetMap.tsx` — renders markers from props; it does not listen to the socket itself.
- `frontend/src/api/agents.ts` — REST client for the initial current-state snapshot (reused for reconnect resync).

**Contract**

- `docs/ws-protocol.md` — the wire contract, written before the code so both sides conform.

## Event

- **Name:** `agent.telemetry.updated` (backend → frontend, broadcast).
- **Payload purpose:** carries only `agent_id` and `latest_state` (`lat`, `lng`,
  `speed`, `battery`, `status`, `recorded_at`) so the frontend can replace one
  agent's `latest_state` in place. Stable identity (`name`, `type`) is omitted —
  the client already has it from the snapshot.

## Important decisions

- **REST snapshot first, Socket.IO deltas afterward.** The event carries a single
  agent and partial identity, so a fresh client needs the full snapshot first;
  events then keep it live.
- **Emit after Postgres and Redis.** Postgres commits first (durable source of
  truth), then Redis is updated, and only then is the event emitted — so no event
  describes state a later failure could roll back.
- **Emit is best-effort.** Durability is already achieved before the emit; a
  failed push logs a warning and still returns the stored row instead of failing
  the request.
- **Shared frontend socket instance.** One module-level socket for the whole app,
  with `autoConnect: false` so importing it has no side effect and React controls
  the connection lifecycle.
- **Functional, immutable React state update.** `setAgents((current) => ...)`
  reads the latest state (no stale closure) and returns a new array with a new
  object only for the matching agent, so React re-renders correctly.

## Connection status & reconnect resync

This hardening sits on top of the live-push MVP. It is **frontend-only**
(`App.tsx`, `App.css`) — no backend, socket-config, or contract changes.

**Completed behavior:**

- **Connection indicator.** A typed `ConnectionStatus` (`connecting | connected |
  disconnected`) drives a compact header pill: `connected → "Live"`,
  `connecting → "Reconnecting"`, `disconnected → "Disconnected"`. Transitions:
  initial `connecting`; socket `connect → connected`; socket `disconnect →
  disconnected`; Manager `reconnect_attempt → connecting`.
- **Automatic reconnect.** Socket.IO's default — the Manager (`socket.io`)
  re-establishes the transport; no configuration changed.
- **REST resync on reconnect.** A `reconnect` listener on the Manager fires **only
  after a successful re-connection, never on the first connect**, so it is the
  safe trigger for a resync that is not redundant with the initial snapshot load.
  It calls `getCurrentState()` and **replaces** the whole `agents` array with the
  authoritative snapshot — a replace, not a merge, because REST is authoritative
  and a partial merge could leave stale `latest_state` behind. On failure it keeps
  the existing state and logs a console error (no crash). `LAST SYNC` updates.
- **Cleanup / StrictMode.** All listeners, including the two Manager listeners
  (`reconnect_attempt`, `reconnect`), are removed by named reference on cleanup,
  so StrictMode's dev remount does not accumulate listeners or fire a duplicate
  resync (its manual disconnect/connect fires `connect`, not `reconnect`).

## Verification performed

- **Backend tests:** `backend/tests/test_telemetry_service.py` proves ordering
  (insert → commit → refresh → Redis → emit), that a Redis failure skips the
  emit, that an emit failure is best-effort and logged, and that an unknown agent
  raises before any side effect.
- **Frontend build:** `npm run build` (`tsc --noEmit && vite build`) passes.
- **Live UI:** with backend and frontend running, telemetry sent via the
  simulator/Postman is received over the socket and the UI updates without a
  refresh.
- **Reconnect/resync (manual):** stopping the real backend flips the header to
  "Disconnected" then "Reconnecting"; restarting it returns to "Live", and on
  reconnect the dashboard re-fetches `current-state`, replaces the agents array,
  and corrects any state missed during the outage — no browser refresh.

## Unknown-agent recovery & env-based socket URL (completed)

- **Env-based socket URL.** The backend Socket.IO origin is read from
  `import.meta.env.VITE_SOCKET_URL` (see `frontend/.env.example`); the client
  fails fast if it is missing rather than connecting to an implicit origin. No
  hardcoded origin remains in runtime code.
- **Unknown-agent recovery.** An `agent.telemetry.updated` event for an
  `agent_id` not in the snapshot triggers a single, deduplicated re-fetch of
  `GET /api/agents/current-state` that replaces the whole agents array (no
  partial agent is appended, since the event lacks `name`/`type`). Reconnect
  resync and unknown-agent recovery share one resync function guarded by an
  in-flight ref, so concurrent/repeated triggers cause at most one REST request;
  a failed resync preserves state and logs the reason (incl. the `agent_id`).
  Once the snapshot includes the agent, its later events use the incremental path.

## Deferred items (hardening still open)

- Socket authentication / RBAC on socket actions.
- Redis pub/sub fan-out for multiple backend workers.
- UI backpressure / throttling.
- Alerts events.
- Commands and ACK events.
- Presence.
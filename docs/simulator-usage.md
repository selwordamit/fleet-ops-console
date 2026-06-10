# Simulator Usage

A practical guide to running the Fleet Operations Console simulator.

The simulator is a standalone Python service that behaves like external fleet hardware: it registers fake agents and continuously POSTs telemetry **through the backend REST API only**. It is the easiest way to populate the map, exercise ingestion, and drive demos.

---

## What the simulator does

- Registers fake agents through `POST /api/agents`.
- Sends telemetry for each agent on a loop through `POST /api/agents/{id}/telemetry`.
- Places agents in one of two **controlled** modes:
  - `local_cluster` — a deterministic spread of `AGENT_COUNT` agents around one base location. Good for testing map clustering and load.
  - `fixed_points` — exact agent locations loaded from a scenario JSON file. Good for stable, repeatable demos.
- Moves each agent with a small controlled step per tick, drains battery, and reports a status (`idle`, `en-route`, `stopped`, `offline`) — `en-route` is weighted most likely, and only moving agents report a non-zero speed.
- Is configured entirely through environment variables — no code changes needed to change how it runs.

## What the simulator does NOT do

- It never touches Postgres or Redis directly — all data flows through the backend REST API.
- It does not place agents randomly across the country; placement is always controlled (`local_cluster` around a base point, or `fixed_points` from a file).
- It does not reuse, upsert, or reset agents — **every run registers a brand-new set of agents**.
- It does not use WebSocket and does not receive or acknowledge commands.
- It does not send asynchronously or in batches — requests are sequential and synchronous (one HTTP request per agent per tick).
- It has no Dockerfile / Compose wiring yet; it is run locally.

---

## Required services before running

The simulator only talks to the backend, but the backend needs its dependencies. Bring these up first:

1. **PostgreSQL** — durable telemetry/agent storage (via `docker compose up postgres`).
2. **Redis** — latest-state cache (via `docker compose up redis`).
3. **Backend server** — the FastAPI app the simulator POSTs to.

Start the backend from `backend/`:

```bash
python -m uvicorn app.main:app --reload
```

Verify it is reachable: `GET http://localhost:8000/health` → `{"status": "ok"}`.

---

## Install simulator requirements

From the repo root:

```bash
pip install -r simulator/requirements.txt
```

(The only runtime dependency is `requests`.)

---

## Run with Docker Compose (backend + simulator + Postgres + Redis)

The backend and simulator are containerized. Compose brings up Postgres, Redis, the backend (which applies migrations on startup), and the simulator together. The simulator container reaches the backend at `http://backend:8000` and still talks **only** to the backend REST API — never to Postgres or Redis directly.

From the repo root:

```bash
docker compose up --build
```

This builds and starts `postgres`, `redis`, `backend`, and `simulator`. The frontend is **not** built (it lives behind the `frontend` compose profile and is not implemented yet). The equivalent explicit form is:

```bash
docker compose up --build postgres redis backend simulator
```

Startup ordering is handled by health checks: the backend waits for Postgres and Redis to be healthy, and the simulator waits for the backend's `/health` to return `200` before it starts registering agents.

Container simulator settings are provided in `docker-compose.yml` (`environment:`): `BACKEND_URL=http://backend:8000`, `SIMULATION_MODE=local_cluster`, `AGENT_COUNT=3`, `TELEMETRY_INTERVAL_SECONDS=2`. Change the count/mode there (or with `-e` overrides) and re-run.

Stop everything with `Ctrl+C`, then `docker compose down` (add `-v` to also drop the Postgres volume for a clean slate).

> The sections below describe running the simulator **directly on the host** (without its container), which is still fully supported for quick local iteration.

---

## Running the simulator (on the host)

Always run as a module from the **repo root** so package imports and the default scenario path resolve correctly:

```bash
python -m simulator.app.main
```

The simulator logs its loaded config once at startup, then logs a line per telemetry tick (e.g. `Telemetry tick: 3/3 sent`). Stop it with **Ctrl+C**.

### Configuration (environment variables)

| Variable | Default | Used by | Meaning |
| --- | --- | --- | --- |
| `BACKEND_URL` | `http://localhost:8000` | both | Backend API base URL. |
| `SIMULATION_MODE` | `local_cluster` | both | `local_cluster` or `fixed_points`. |
| `AGENT_COUNT` | `10` | `local_cluster` | Number of agents to generate (ignored in `fixed_points`). |
| `TELEMETRY_INTERVAL_SECONDS` | `2` | both | Seconds between telemetry ticks. |
| `BASE_LAT` | `32.0853` | `local_cluster` | Base latitude (default Tel Aviv). |
| `BASE_LNG` | `34.7818` | `local_cluster` | Base longitude (default Tel Aviv). |
| `SPREAD_RADIUS_KM` | `2` | `local_cluster` | Radius around the base point. |
| `SCENARIO_FILE` | `simulator/scenarios/israel_demo.json` | `fixed_points` | Path to the scenario JSON file. |

> Examples below show **bash** first, then the **PowerShell** equivalent (this project runs on Windows). In PowerShell, set variables with `$env:NAME = "value"` before the run command.

### Default mode

```bash
python -m simulator.app.main
```

```powershell
python -m simulator.app.main
```

Runs `local_cluster` with 10 agents around Tel Aviv at a 2-second interval.

### local_cluster with 3 agents (used for the verification run)

```bash
SIMULATION_MODE=local_cluster AGENT_COUNT=3 python -m simulator.app.main
```

```powershell
$env:SIMULATION_MODE = "local_cluster"; $env:AGENT_COUNT = "3"; python -m simulator.app.main
```

### 7 agents

```bash
SIMULATION_MODE=local_cluster AGENT_COUNT=7 python -m simulator.app.main
```

```powershell
$env:SIMULATION_MODE = "local_cluster"; $env:AGENT_COUNT = "7"; python -m simulator.app.main
```

### 214 agents

For larger counts, consider a larger interval so the sequential, synchronous sends keep up:

```bash
SIMULATION_MODE=local_cluster AGENT_COUNT=214 TELEMETRY_INTERVAL_SECONDS=5 python -m simulator.app.main
```

```powershell
$env:SIMULATION_MODE = "local_cluster"; $env:AGENT_COUNT = "214"; $env:TELEMETRY_INTERVAL_SECONDS = "5"; python -m simulator.app.main
```

### fixed_points mode

Uses the scenario file instead of generating agents. `AGENT_COUNT` is ignored — the number of agents equals the number of entries in the file.

```bash
SIMULATION_MODE=fixed_points python -m simulator.app.main
```

```powershell
$env:SIMULATION_MODE = "fixed_points"; python -m simulator.app.main
```

To use a different scenario file:

```bash
SIMULATION_MODE=fixed_points SCENARIO_FILE=simulator/scenarios/my_demo.json python -m simulator.app.main
```

```powershell
$env:SIMULATION_MODE = "fixed_points"; $env:SCENARIO_FILE = "simulator/scenarios/my_demo.json"; python -m simulator.app.main
```

> PowerShell keeps `$env:` variables for the rest of the session. Open a new shell, or clear them (e.g. `Remove-Item Env:AGENT_COUNT`), before a run that should use defaults.

---

## Creating / editing a scenario JSON file

A scenario file is a JSON **list** of agent objects. Each entry must include all of these fields:

- `name` — agent name (string)
- `type` — vehicle type, e.g. `truck`, `van`, `scooter` (string)
- `status` — one of `idle`, `en-route`, `stopped`, `offline` (validated by the backend)
- `lat` — starting latitude (number)
- `lng` — starting longitude (number)

A missing field on any entry, or a top-level value that is not a list, makes the run fail fast with a clear error. Relative paths are resolved from the repo root; absolute paths are used as-is. See `simulator/scenarios/israel_demo.json` for a working example.

### Example: 5 vehicles in Tel Aviv and 1 in Jerusalem

`simulator/scenarios/tlv_plus_jerusalem.json`:

```json
[
  { "name": "tlv-1", "type": "truck",   "status": "en-route", "lat": 32.0853, "lng": 34.7818 },
  { "name": "tlv-2", "type": "van",     "status": "idle",     "lat": 32.0700, "lng": 34.7900 },
  { "name": "tlv-3", "type": "scooter", "status": "stopped",  "lat": 32.0900, "lng": 34.7750 },
  { "name": "tlv-4", "type": "truck",   "status": "en-route", "lat": 32.0800, "lng": 34.7850 },
  { "name": "tlv-5", "type": "van",     "status": "idle",     "lat": 32.0650, "lng": 34.8000 },
  { "name": "jerusalem-1", "type": "truck", "status": "en-route", "lat": 31.7683, "lng": 35.2137 }
]
```

Run it:

```bash
SIMULATION_MODE=fixed_points SCENARIO_FILE=simulator/scenarios/tlv_plus_jerusalem.json python -m simulator.app.main
```

```powershell
$env:SIMULATION_MODE = "fixed_points"; $env:SCENARIO_FILE = "simulator/scenarios/tlv_plus_jerusalem.json"; python -m simulator.app.main
```

---

## How to verify

While the simulator runs (Postgres + Redis + backend up):

**1. Agents created through the API**

```bash
docker compose exec postgres psql -U fleetops -d fleetops -c "SELECT id, name, type, status FROM agents;"
```

The simulator's agents appear as rows.

**2. Telemetry persisted in Postgres**

```bash
docker compose exec postgres psql -U fleetops -d fleetops -c "SELECT count(*) FROM telemetry;"
```

The count increases on each tick.

**3. Redis latest state updated**

```bash
docker compose exec redis redis-cli KEYS "agent:*:state"
docker compose exec redis redis-cli GET "agent:1:state"
```

There is one `agent:{id}:state` key per registered agent, holding the latest telemetry snapshot.

**4. Current-state API shows the simulator data**

```text
GET http://localhost:8000/api/agents/current-state
  → 200 OK, the simulator agents with populated "latest_state"
```

---

## Dev cleanup (local development only)

Repeated runs accumulate new agents (there is no reuse/reset yet). To start fresh in local dev:

**Postgres** — clear telemetry and agents and reset IDs:

```sql
TRUNCATE telemetry, agents RESTART IDENTITY CASCADE;
```

```bash
docker compose exec postgres psql -U fleetops -d fleetops -c "TRUNCATE telemetry, agents RESTART IDENTITY CASCADE;"
```

**Redis** — clear the cached latest-state keys:

```bash
docker compose exec redis redis-cli FLUSHDB
```

> ⚠️ **Warning:** these commands wipe data and are for **local development only**. Never run them against a shared or production database/cache.

---

## Known tradeoffs and future improvements

- **Repeated runs create new agents** — there is no reuse/upsert, so cleanup is currently manual (above). A future reuse/upsert/reset mode would let runs reattach to existing agents.
- `local_cluster` movement is a **controlled random walk**, not real route/road simulation.
- Sends are **sequential and synchronous** — high agent counts (e.g. ~1000) may need a larger `TELEMETRY_INTERVAL_SECONDS`, or future async/batched sending.
- **No Dockerfile / Compose wiring** for the simulator yet — it is run locally.
- **No command/ACK support** yet — the simulator cannot receive or acknowledge commands.

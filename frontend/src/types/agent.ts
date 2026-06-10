// Client-side mirror of the backend response for GET /api/agents/current-state.
// Source of truth: backend/app/schemas/agent.py (AgentCurrentState / AgentLatestState).
// Keep these in sync with that schema.

// Allowed operational status values. Mirrors backend AgentStatus (enums.py).
// Used for both the stored agent status and the latest telemetry status.
export type AgentStatus = "idle" | "en-route" | "stopped" | "offline";

// An agent's latest reported telemetry, sourced from the backend's Redis
// current-state snapshot. datetimes arrive as ISO 8601 strings over JSON.
export interface AgentLatestState {
  lat: number;
  lng: number;
  speed: number;
  battery: number;
  status: AgentStatus;
  recorded_at: string;
}

// An agent's identity plus its latest state. latest_state is null when the agent
// is registered in Postgres but has not reported telemetry yet.
export interface AgentCurrentState {
  id: number;
  name: string;
  type: string;
  status: AgentStatus;
  last_seen: string | null;
  latest_state: AgentLatestState | null;
}

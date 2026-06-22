import type { AgentStatus } from "./agent";

// One agent's telemetry within a batch. Flat shape (no nested latest_state) and
// notably no recorded_at — the batch's envelope `ts` is the recorded time for
// every item in that flush window.
export interface AgentTelemetryBatchItem {
  agent_id: number;
  lat: number;
  lng: number;
  speed: number;
  battery: number;
  status: AgentStatus;
}

// Single broadcast emitted once per batcher flush, carrying every agent that
// reported in that window. Replaces the per-agent agent.telemetry.updated event.
export interface AgentTelemetryBatchEvent {
  type: "agent.telemetry.batch";
  payload: AgentTelemetryBatchItem[];
  ts: string;
}

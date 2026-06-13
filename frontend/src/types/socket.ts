import type { AgentLatestState } from "./agent";

export interface AgentTelemetryUpdatedPayload {
  agent_id: number;
  latest_state: AgentLatestState;
}

export interface AgentTelemetryUpdatedEvent {
  type: "agent.telemetry.updated";
  payload: AgentTelemetryUpdatedPayload;
  ts: string;
  requestId: string | null;
}

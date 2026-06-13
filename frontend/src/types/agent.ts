
export type AgentStatus = "idle" | "en-route" | "stopped" | "offline";

export interface AgentLatestState {
  lat: number;
  lng: number;
  speed: number;
  battery: number;
  status: AgentStatus;
  recorded_at: string;
}

export interface AgentCurrentState {
  id: number;
  name: string;
  type: string;
  status: AgentStatus;
  last_seen: string | null;
  latest_state: AgentLatestState | null;
}

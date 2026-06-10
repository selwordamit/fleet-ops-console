import type { AgentCurrentState } from "../types/agent";

// REST client for the agents current-state endpoint. Uses a same-origin
// relative path so the Vite dev proxy (/api -> backend) handles forwarding;
// the backend host is never hardcoded here.
export async function getCurrentState(): Promise<AgentCurrentState[]> {
  const response = await fetch("/api/agents/current-state");

  if (!response.ok) {
    throw new Error(
      `Failed to load agents current-state: ${response.status} ${response.statusText}`,
    );
  }

  return (await response.json()) as AgentCurrentState[];
}

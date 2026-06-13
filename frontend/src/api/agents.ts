import type { AgentCurrentState } from "../types/agent";

export async function getCurrentState(): Promise<AgentCurrentState[]> {
  const response = await fetch("/api/agents/current-state");

  if (!response.ok) {
    throw new Error(
      `Failed to load agents current-state: ${response.status} ${response.statusText}`,
    );
  }

  return (await response.json()) as AgentCurrentState[];
}

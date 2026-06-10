import { useEffect, useState } from "react";

import "./App.css";
import { getCurrentState } from "./api/agents";
import AgentsTable from "./features/agents/AgentsTable";
import type { AgentCurrentState } from "./types/agent";

// Owns the data lifecycle and the dashboard structure. Styling lives in App.css;
// row rendering lives in AgentsTable.
export default function App() {
  const [agents, setAgents] = useState<AgentCurrentState[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getCurrentState()
      .then((data) => setAgents(data))
      .catch((err) => setError(err instanceof Error ? err.message : String(err)));
  }, []);

  // Summary is derived from the loaded agents; null latest_state = no live telemetry.
  const total = agents?.length ?? 0;
  const withTelemetry = agents?.filter((a) => a.latest_state !== null).length ?? 0;
  const withoutTelemetry = total - withTelemetry;

  return (
    <div className="foc-shell">
      <div className="foc-container">
        <header className="foc-header">
          <div className="foc-brand">
            <span className="foc-logo" />
            <div>
              <h1 className="foc-title">Fleet Operations Console</h1>
              <p className="foc-subtitle">Fleet current-state snapshot</p>
            </div>
          </div>
        </header>

        {error !== null ? (
          <div className="foc-panel">
            <div className="foc-message">Failed to load agents: {error}</div>
          </div>
        ) : agents === null ? (
          <div className="foc-panel">
            <div className="foc-message">Loading agents…</div>
          </div>
        ) : (
          <>
            <section className="foc-stats">
              <div className="foc-stat">
                <div className="foc-stat__label">Total agents</div>
                <div className="foc-stat__value">{total}</div>
              </div>
              <div className="foc-stat">
                <div className="foc-stat__label">With current state</div>
                <div className="foc-stat__value foc-stat__value--accent">{withTelemetry}</div>
              </div>
              <div className="foc-stat">
                <div className="foc-stat__label">Without current state</div>
                <div className="foc-stat__value foc-stat__value--muted">{withoutTelemetry}</div>
              </div>
            </section>

            <div className="foc-main">
              <section className="foc-panel foc-panel--map">
                <div className="foc-panel__head">
                  <span className="foc-panel__title">Map Preview</span>
                </div>
                <div className="foc-map">
                  <span className="foc-map__tag">Placeholder</span>
                  <div className="foc-map__title">Map placeholder</div>
                  <p className="foc-map__sub">
                    Leaflet + OpenStreetMap will be added in the next checkpoint.
                  </p>
                </div>
              </section>

              <section className="foc-panel">
                <div className="foc-panel__head">
                  <span className="foc-panel__title">Agents</span>
                  <span className="foc-panel__count">{total} total</span>
                </div>
                <AgentsTable agents={agents} />
              </section>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

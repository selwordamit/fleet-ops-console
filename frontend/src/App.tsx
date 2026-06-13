import { useEffect, useState } from "react";

import "./App.css";
import { getCurrentState } from "./api/agents";
import AgentsTable from "./features/agents/AgentsTable";
import FleetMap from "./features/map/FleetMap";
import type { AgentCurrentState, AgentStatus } from "./types/agent";
import { socket } from "./realtime/socket";
import type { AgentTelemetryUpdatedEvent } from "./types/socket";

// Sidebar filter keys: every status, plus "all" and the no-telemetry bucket.
type FilterKey = AgentStatus | "all" | "no-telemetry";

const STATUS_LEGEND: { key: AgentStatus; label: string }[] = [
  { key: "en-route", label: "En-route" },
  { key: "idle", label: "Idle" },
  { key: "stopped", label: "Stopped" },
  { key: "offline", label: "Offline" },
];

// Deferred capabilities, shown honestly as "not built yet" rather than as fake
// working UI. These map to later build-order phases (WebSocket, alerts, commands).
const COMING_NEXT = [
  { title: "Live telemetry stream", note: "Push updates without manual refresh", tag: "Requires WebSocket" },
  { title: "Alerts & notifications", note: "Low battery, speeding, offline", tag: "Coming next" },
  { title: "Operator commands", note: "Ping · Recall · Set status", tag: "Coming next" },
];

// Relative "x ago" from an ISO timestamp, for the selected-agent last-seen field.
function timeAgo(iso: string): string {
  const sec = Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / 1000));
  if (sec < 60) return `${sec}s ago`;
  if (sec < 3600) return `${Math.floor(sec / 60)}m ago`;
  return `${Math.floor(sec / 3600)}h ago`;
}

// Owns the data lifecycle and the dashboard structure. Styling lives in App.css.
// Selection and filtering are local view state derived over the real
// current-state array; no extra fetching, no mock data.
export default function App() {
  const [agents, setAgents] = useState<AgentCurrentState[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [filter, setFilter] = useState<FilterKey>("all");
  const [lastSync, setLastSync] = useState<Date | null>(null);

  useEffect(() => {
    getCurrentState()
      .then((data) => {
        setAgents(data);
        setLastSync(new Date());
      })
      .catch((err) => setError(err instanceof Error ? err.message : String(err)));
  }, []);

  // Socket.IO lifecycle for the whole App. This checkpoint only logs events to
  // the console — it does not yet update agent state or move markers. Named
  // handlers give stable references so cleanup can remove exactly these.
  useEffect(() => {
    function onConnect() {
      console.log("[socket] connected:", socket.id);
    }
    function onDisconnect(reason: string) {
      console.log("[socket] disconnected:", reason);
    }
    function onConnectionReady(payload: unknown) {
      console.log("[socket] connection.ready:", payload);
    }
    function onTelemetryUpdated(event: AgentTelemetryUpdatedEvent) {
      console.log("[socket] agent.telemetry.updated:", event);

      const { agent_id, latest_state } = event.payload;
      // Functional update: read React's latest agents, not the value captured
      // when this once-only effect mounted.
      setAgents((currentAgents) => {
        if (currentAgents === null) return currentAgents;
        // Unknown agent id (not in the loaded snapshot): leave state unchanged
        // for this checkpoint, so React does not re-render.
        if (!currentAgents.some((a) => a.id === agent_id)) return currentAgents;
        // Immutable replace: new array, new object only for the matching agent,
        // all other agents returned by reference unchanged.
        return currentAgents.map((a) =>
          a.id === agent_id ? { ...a, latest_state } : a,
        );
      });
    }

    // Register before connecting so the immediate connect/connection.ready
    // events are not missed.
    socket.on("connect", onConnect);
    socket.on("disconnect", onDisconnect);
    socket.on("connection.ready", onConnectionReady);
    socket.on("agent.telemetry.updated", onTelemetryUpdated);

    socket.connect();

    return () => {
      socket.off("connect", onConnect);
      socket.off("disconnect", onDisconnect);
      socket.off("connection.ready", onConnectionReady);
      socket.off("agent.telemetry.updated", onTelemetryUpdated);
      socket.disconnect();
    };
  }, []);

  // Derived summary over the real, already-loaded agents.
  const list = agents ?? [];
  const total = list.length;
  const withTelemetry = list.filter((a) => a.latest_state !== null).length;
  const withoutTelemetry = total - withTelemetry;

  const statusCounts: Record<AgentStatus, number> = {
    "en-route": 0,
    idle: 0,
    stopped: 0,
    offline: 0,
  };
  list.forEach((a) => {
    if (a.latest_state) statusCounts[a.latest_state.status] += 1;
  });

  const matchesFilter = (a: AgentCurrentState) => {
    if (filter === "all") return true;
    if (filter === "no-telemetry") return a.latest_state === null;
    return a.latest_state?.status === filter;
  };
  const filtered = list.filter(matchesFilter);
  const selected = list.find((a) => a.id === selectedId) ?? null;

  const filterDefs: { key: FilterKey; label: string; count: number }[] = [
    { key: "all", label: "All", count: total },
    { key: "en-route", label: "En-route", count: statusCounts["en-route"] },
    { key: "idle", label: "Idle", count: statusCounts.idle },
    { key: "stopped", label: "Stopped", count: statusCounts.stopped },
    { key: "offline", label: "Offline", count: statusCounts.offline },
    { key: "no-telemetry", label: "No telemetry", count: withoutTelemetry },
  ];

  const selectedState = selected?.latest_state ?? null;

  return (
    <div className="foc-app">
      <header className="foc-topbar">
        <span className="foc-logo" />
        <span className="foc-brand-title">Fleet Operations Console</span>
        <span className="foc-topbar__spacer" />
        <div className="foc-sync">
          <span className="foc-sync__label">Last sync</span>
          <span className="foc-sync__value">{lastSync ? lastSync.toLocaleTimeString() : "—"}</span>
        </div>
      </header>

      <div className="foc-body">
        {/* LEFT: fleet summary + agent list */}
        <aside className="foc-side foc-side--left">
          <div className="foc-summary">
            <div className="foc-section-label">Fleet summary</div>
            <div className="foc-stat-grid">
              <div className="foc-stat-card">
                <div className="foc-stat-card__value">{total}</div>
                <div className="foc-stat-card__label">Total agents</div>
              </div>
              <div className="foc-stat-card">
                <div className="foc-stat-card__value foc-stat-card__value--accent">{withTelemetry}</div>
                <div className="foc-stat-card__label">Reporting</div>
              </div>
            </div>
            <div className="foc-legend">
              {STATUS_LEGEND.map((s) => (
                <span className="foc-legend__item" key={s.key}>
                  <span className={`foc-legend__dot foc-dot--${s.key}`} />
                  <span className="foc-legend__label">{s.label}</span>
                  <span className="foc-legend__count">{statusCounts[s.key]}</span>
                </span>
              ))}
            </div>
          </div>

          <div className="foc-filters">
            {filterDefs.map((f) => (
              <button
                type="button"
                key={f.key}
                className={`foc-chip${filter === f.key ? " foc-chip--active" : ""}`}
                onClick={() => setFilter(f.key)}
              >
                {f.label} <span className="foc-chip__count">{f.count}</span>
              </button>
            ))}
          </div>

          {error !== null ? (
            <div className="foc-msg">Failed to load agents: {error}</div>
          ) : agents === null ? (
            <div className="foc-msg">Loading agents…</div>
          ) : (
            <AgentsTable agents={filtered} selectedId={selectedId} onSelect={setSelectedId} />
          )}
        </aside>

        {/* CENTER: map */}
        <main className="foc-mapwrap">
          <FleetMap agents={list} selectedId={selectedId} onSelect={setSelectedId} />

          <div className="foc-map-overlay foc-map-overlay--top">
            <span className="foc-overlay__label">Operational map</span>
            <span className="foc-overlay__sep" />
            <span className="foc-overlay__plotted">{withTelemetry} plotted</span>
            <span className="foc-overlay__muted">· {withoutTelemetry} unplotted</span>
            <span className="foc-overlay__sep" />
            <span className="foc-overlay__muted">Live updates</span>
            <span className="foc-deferred">Requires WebSocket</span>
          </div>

          <div className="foc-map-overlay foc-map-overlay--bottom">
            <div className="foc-section-label">Status</div>
            <div className="foc-map-legend">
              {STATUS_LEGEND.map((s) => (
                <span className="foc-legend__item" key={s.key}>
                  <span className={`foc-legend__dot foc-dot--${s.key}`} />
                  <span className="foc-legend__label">{s.label}</span>
                </span>
              ))}
            </div>
          </div>
        </main>

        {/* RIGHT: selected agent detail + deferred sections */}
        <aside className="foc-side foc-side--right foc-scroll">
          {selected !== null ? (
            <div className="foc-detail">
              <div className="foc-detail__head">
                <div>
                  <div className="foc-detail__name">{selected.name}</div>
                  <div className="foc-detail__type">{selected.type}</div>
                </div>
                {selectedState !== null ? (
                  <span className={`foc-badge foc-badge--${selectedState.status}`}>{selectedState.status}</span>
                ) : (
                  <span className="foc-badge foc-badge--none">offline</span>
                )}
              </div>

              {selectedState !== null ? (
                <>
                  <div className="foc-metric-grid">
                    <div className="foc-metric-card">
                      <div className="foc-metric-card__label">Battery</div>
                      <div
                        className={`foc-metric-card__value${
                          selectedState.battery < 15 ? " foc-metric-card__value--danger" : ""
                        }`}
                      >
                        {selectedState.battery.toFixed(0)}%
                      </div>
                    </div>
                    <div className="foc-metric-card">
                      <div className="foc-metric-card__label">Speed</div>
                      <div className="foc-metric-card__value">{selectedState.speed.toFixed(0)} km/h</div>
                    </div>
                    <div className="foc-metric-card">
                      <div className="foc-metric-card__label">Status</div>
                      <div className={`foc-metric-card__value foc-metric-card__value--${selectedState.status}`}>
                        {selectedState.status}
                      </div>
                    </div>
                    <div className="foc-metric-card">
                      <div className="foc-metric-card__label">Last seen</div>
                      <div className="foc-metric-card__value">{timeAgo(selectedState.recorded_at)}</div>
                    </div>
                  </div>

                  <div className="foc-pos">
                    <div className="foc-metric-card__label">Position</div>
                    <div className="foc-pos__row">
                      <span>Latitude</span>
                      <span className="foc-pos__value">{selectedState.lat.toFixed(5)}</span>
                    </div>
                    <div className="foc-pos__row">
                      <span>Longitude</span>
                      <span className="foc-pos__value">{selectedState.lng.toFixed(5)}</span>
                    </div>
                    <div className="foc-pos__row">
                      <span>Recorded</span>
                      <span className="foc-pos__value">
                        {new Date(selectedState.recorded_at).toLocaleTimeString()}
                      </span>
                    </div>
                  </div>
                </>
              ) : (
                <div className="foc-notelem">
                  <div className="foc-notelem__title">No telemetry yet</div>
                  <div className="foc-notelem__sub">
                    Registered in Postgres but has not reported a current state to Redis.
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="foc-empty">
              <div className="foc-empty__title">No agent selected</div>
              <div className="foc-empty__sub">
                Select an agent from the list or a marker on the map to inspect its current state.
              </div>
            </div>
          )}

          <div className="foc-coming">
            <div className="foc-section-label">Coming next</div>
            {COMING_NEXT.map((c) => (
              <div className="foc-coming__card" key={c.title}>
                <div className="foc-coming__text">
                  <div className="foc-coming__title">{c.title}</div>
                  <div className="foc-coming__note">{c.note}</div>
                </div>
                <span className="foc-deferred">{c.tag}</span>
              </div>
            ))}
          </div>
        </aside>
      </div>
    </div>
  );
}
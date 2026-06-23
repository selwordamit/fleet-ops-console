import { useEffect, useRef, useState } from "react";

import "./App.css";
import { getCurrentState } from "./api/agents";
import AgentsTable from "./features/agents/AgentsTable";
import FleetMap from "./features/map/FleetMap";
import type { AgentCurrentState, AgentLatestState, AgentStatus } from "./types/agent";
import { socket } from "./realtime/socket";
import type { AgentTelemetryBatchEvent } from "./types/socket";

// Sidebar filter keys: every status, plus "all" and the no-telemetry bucket.
type FilterKey = AgentStatus | "all" | "no-telemetry";

// Socket.IO connection status, surfaced as a compact header indicator.
type ConnectionStatus = "connecting" | "connected" | "disconnected";

const CONNECTION_LABEL: Record<ConnectionStatus, string> = {
  connected: "Live",
  connecting: "Reconnecting",
  disconnected: "Disconnected",
};

const STATUS_LEGEND: { key: AgentStatus; label: string }[] = [
  { key: "en-route", label: "En-route" },
  { key: "idle", label: "Idle" },
  { key: "stopped", label: "Stopped" },
  { key: "offline", label: "Offline" },
];

// Capability cards. Live telemetry is now active via Socket.IO; alerts and
// commands are still deferred to later build-order phases and shown honestly as
// "coming next" rather than as fake working UI.
const COMING_NEXT = [
  { title: "Live telemetry stream", note: "Push updates without manual refresh", tag: "Live via Socket.IO" },
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
  // Starts as "connecting": the socket effect calls socket.connect() on mount.
  const [status, setStatus] = useState<ConnectionStatus>("connecting");

  // Mirror of `agents` for synchronous reads inside the once-registered socket
  // handlers (which would otherwise close over stale state). Kept in lockstep by
  // the effect below and eagerly on resync.
  const agentsRef = useRef<AgentCurrentState[] | null>(null);
  // Guards against overlapping current-state resyncs (a reconnect and/or repeated
  // unknown-agent events): at most one REST resync is in flight at a time.
  const resyncInProgressRef = useRef(false);
  // Accumulates telemetry updates between 1-second flush ticks. Latest value per
  // agent_id wins when multiple batches arrive within the same tick window.
  const pendingUpdatesRef = useRef<Map<number, AgentLatestState>>(new Map());

  useEffect(() => {
    getCurrentState()
      .then((data) => {
        setAgents(data);
        setLastSync(new Date());
      })
      .catch((err) => setError(err instanceof Error ? err.message : String(err)));
  }, []);

  // Keep the ref aligned with state so socket handlers always see the latest agents.
  useEffect(() => {
    agentsRef.current = agents;
  }, [agents]);

  // Socket.IO lifecycle for the whole App. The client connects, receives
  // agent.telemetry.batch events, and applies each item's latest_state to the
  // existing React agents state so the map, list, and details update live.
  // Named handlers give stable references so cleanup can remove exactly these.
  useEffect(() => {
    // Shared, deduplicated current-state resync used by BOTH a successful
    // reconnect and unknown-agent recovery. REST current-state is authoritative,
    // so the whole agents array is replaced (not merged). At most one resync is in
    // flight at a time; overlapping triggers are skipped. Failures preserve the
    // current state and are logged with the reason (including any unknown agent_id).
    function resyncCurrentState(reason: string) {
      if (resyncInProgressRef.current) {
        console.log("[socket] current-state resync skipped (in progress):", reason);
        return;
      }
      resyncInProgressRef.current = true;
      getCurrentState()
        .then((data) => {
          // Eagerly align the ref so an event arriving right after this resync
          // already sees the new agent as known (closes the dedup window).
          agentsRef.current = data;
          setAgents(data);
          setLastSync(new Date());
        })
        .catch((err) => {
          console.error("[socket] current-state resync failed:", reason, err);
        })
        .finally(() => {
          resyncInProgressRef.current = false;
        });
    }

    function onConnect() {
      console.log("[socket] connected:", socket.id);
      setStatus("connected");
    }
    function onDisconnect(reason: string) {
      console.log("[socket] disconnected:", reason);
      setStatus("disconnected");
    }
    function onConnectionReady(payload: unknown) {
      console.log("[socket] connection.ready:", payload);
    }
    // Manager-level reconnection signals. reconnect_attempt fires while the
    // transport is retrying; reconnect fires only after a *successful*
    // re-connection and never on the first connect — so it is the safe trigger
    // for a REST resync that is not redundant with the initial snapshot load.
    function onReconnectAttempt(attempt: number) {
      console.log("[socket] reconnect attempt:", attempt);
      setStatus("connecting");
    }
    function onReconnect(attempt: number) {
      console.log("[socket] reconnected after attempt:", attempt);
      // Recover any telemetry missed while disconnected via the shared,
      // deduplicated authoritative snapshot resync.
      resyncCurrentState("reconnect");
    }
    function onTelemetryBatch(event: AgentTelemetryBatchEvent) {
      console.log("[socket] agent.telemetry.batch:", event.payload.length, "updates");

      // Decide known-vs-unknown OUTSIDE the state updater: updaters must be pure
      // and may run twice under StrictMode, so no network side effects belong in
      // them. agentsRef gives the latest agents without a stale closure.
      const current = agentsRef.current;
      if (current === null) return; // snapshot not loaded yet — ignore until it is

      const knownIds = new Set(current.map((a) => a.id));

      // Build latest_state per known agent in this batch. The batch items omit
      // recorded_at, so the envelope `ts` is the recorded time for the window.
      const updates = new Map<number, AgentLatestState>();
      let hasUnknown = false;
      for (const item of event.payload) {
        if (!knownIds.has(item.agent_id)) {
          hasUnknown = true;
          continue;
        }
        updates.set(item.agent_id, {
          lat: item.lat,
          lng: item.lng,
          speed: item.speed,
          battery: item.battery,
          status: item.status,
          recorded_at: event.ts,
        });
      }

      if (updates.size > 0) {
        // Merge into the pending map instead of calling setAgents directly.
        // The 1-second flush interval below applies all accumulated updates in
        // one React state update, capping re-renders at 1/s regardless of how
        // many batches arrive.
        for (const [id, state] of updates) {
          pendingUpdatesRef.current.set(id, state);
        }
      }

      // Unknown agents (not in the snapshot) carry no stable identity (name/type),
      // so we must NOT append partial agents. The first such item triggers a single
      // deduplicated authoritative resync; subsequent batches then take the
      // incremental path above.
      if (hasUnknown) {
        resyncCurrentState("unknown agent in batch");
      }
    }

    // Register before connecting so the immediate connect/connection.ready
    // events are not missed.
    socket.on("connect", onConnect);
    socket.on("disconnect", onDisconnect);
    socket.on("connection.ready", onConnectionReady);
    socket.on("agent.telemetry.batch", onTelemetryBatch);
    // Reconnection events live on the Manager (socket.io), not the socket.
    socket.io.on("reconnect_attempt", onReconnectAttempt);
    socket.io.on("reconnect", onReconnect);

    socket.connect();

    return () => {
      socket.off("connect", onConnect);
      socket.off("disconnect", onDisconnect);
      socket.off("connection.ready", onConnectionReady);
      socket.off("agent.telemetry.batch", onTelemetryBatch);
      socket.io.off("reconnect_attempt", onReconnectAttempt);
      socket.io.off("reconnect", onReconnect);
      socket.disconnect();
    };
  }, []);

  // Flush accumulated telemetry updates into React state at most once per second.
  // With 5 000–10 000 agents and batches arriving every 100 ms this keeps
  // re-renders at 1/s instead of 10/s, eliminating the multi-second UI freeze.
  useEffect(() => {
    const id = setInterval(() => {
      if (pendingUpdatesRef.current.size === 0) return;
      // Snapshot and clear before the state update so any events that arrive
      // during the synchronous map() below land in a fresh pending map.
      const snapshot = new Map(pendingUpdatesRef.current);
      pendingUpdatesRef.current.clear();
      setAgents((currentAgents) =>
        currentAgents === null
          ? currentAgents
          : currentAgents.map((a) =>
              snapshot.has(a.id) ? { ...a, latest_state: snapshot.get(a.id)! } : a,
            ),
      );
    }, 1000);
    return () => clearInterval(id);
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
        <div className={`foc-conn foc-conn--${status}`}>
          <span className="foc-conn__dot" />
          <span className="foc-conn__label">{CONNECTION_LABEL[status]}</span>
        </div>
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
            <span className="foc-deferred">Live via Socket.IO</span>
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
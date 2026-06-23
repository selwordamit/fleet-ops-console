import { useRef } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import type { AgentCurrentState, AgentStatus } from "../../types/agent";

interface AgentsTableProps {
  agents: AgentCurrentState[];
  selectedId: number | null;
  onSelect: (id: number) => void;
}

function StatusBadge({ status }: { status: AgentStatus }) {
  return <span className={`foc-badge foc-badge--${status}`}>{status}</span>;
}

// .foc-row: padding 11px*2 + ~31px two-line text block + 1px border-bottom = ~54px.
// 56px gives a small safety margin (box-sizing: border-box is set globally).
const ROW_HEIGHT = 56;

export default function AgentsTable({ agents, selectedId, onSelect }: AgentsTableProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  const virtualizer = useVirtualizer({
    count: agents.length,
    getScrollElement: () => containerRef.current,
    estimateSize: () => ROW_HEIGHT,
    overscan: 5,
  });

  if (agents.length === 0) {
    return <div className="foc-msg">No agents match this filter.</div>;
  }

  return (
    <div ref={containerRef} className="foc-list foc-scroll">
      {/* Single tall div that gives the scrollbar its correct total height.
          Only the rows intersecting the viewport are rendered inside it. */}
      <div style={{ height: `${virtualizer.getTotalSize()}px`, position: "relative" }}>
        {virtualizer.getVirtualItems().map((virtualRow) => {
          const agent = agents[virtualRow.index];
          const state = agent.latest_state;
          const statusKey = state ? state.status : "none";
          const selected = agent.id === selectedId;
          return (
            <button
              type="button"
              key={agent.id}
              onClick={() => onSelect(agent.id)}
              className={`foc-row${selected ? " foc-row--selected" : ""}`}
              style={{
                position: "absolute",
                top: 0,
                left: 0,
                width: "100%",
                height: `${virtualRow.size}px`,
                transform: `translateY(${virtualRow.start}px)`,
              }}
            >
              <span className="foc-row__main">
                <span className={`foc-row__dot foc-dot--${statusKey}`} />
                <span className="foc-row__id">
                  <span className="foc-row__name">{agent.name}</span>
                  <span className="foc-row__type">{agent.type}</span>
                </span>
              </span>
              <span className="foc-row__aside">
                {state ? (
                  <StatusBadge status={state.status} />
                ) : (
                  <span className="foc-badge foc-badge--none">no telem.</span>
                )}
                <span className="foc-row__meta">
                  {state ? `${state.battery.toFixed(0)}% · ${state.speed.toFixed(0)} km/h` : "no data"}
                </span>
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

import type { AgentCurrentState, AgentStatus } from "../../types/agent";


interface AgentsTableProps {
  agents: AgentCurrentState[];
  selectedId: number | null;
  onSelect: (id: number) => void;
}

// Status badge: one variant class per valid AgentStatus value.
function StatusBadge({ status }: { status: AgentStatus }) {
  return <span className={`foc-badge foc-badge--${status}`}>{status}</span>;
}

export default function AgentsTable({ agents, selectedId, onSelect }: AgentsTableProps) {
  if (agents.length === 0) {
    return <div className="foc-msg">No agents match this filter.</div>;
  }

  return (
    <div className="foc-list foc-scroll">
      {agents.map((agent) => {
        const state = agent.latest_state;
        const statusKey = state ? state.status : "none";
        const selected = agent.id === selectedId;
        return (
          <button
            type="button"
            key={agent.id}
            onClick={() => onSelect(agent.id)}
            className={`foc-row${selected ? " foc-row--selected" : ""}`}
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
  );
}
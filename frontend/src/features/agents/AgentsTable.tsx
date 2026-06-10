import type { AgentCurrentState, AgentStatus } from "../../types/agent";

// Presentational table for the agents current-state view. Receives the already
// loaded agents and renders them; it never calls the backend itself. Styling
// comes from App.css class names.
interface AgentsTableProps {
  agents: AgentCurrentState[];
}

// Telemetry columns that follow Status and only exist when latest_state is set:
// Lat, Lng, Speed, Battery, Recorded At.
const TELEMETRY_COLUMN_COUNT = 5;

// Status badge: one variant class per valid AgentStatus value.
function StatusBadge({ status }: { status: AgentStatus }) {
  return <span className={`foc-badge foc-badge--${status}`}>{status}</span>;
}

export default function AgentsTable({ agents }: AgentsTableProps) {
  return (
    <div className="foc-table-wrap">
      <table className="foc-table">
        <thead>
          <tr>
            <th className="foc-th--data">ID</th>
            <th>Name</th>
            <th>Type</th>
            <th>Status</th>
            <th className="foc-th--data">Lat</th>
            <th className="foc-th--data">Lng</th>
            <th className="foc-th--data">Speed</th>
            <th className="foc-th--data">Battery</th>
            <th className="foc-th--data">Recorded At</th>
          </tr>
        </thead>
        <tbody>
          {agents.length === 0 ? (
            <tr>
              <td className="foc-muted" colSpan={9}>
                No agents registered.
              </td>
            </tr>
          ) : (
            agents.map((agent) => {
              const state = agent.latest_state;
              return (
                <tr key={agent.id}>
                  <td className="foc-num">{agent.id}</td>
                  <td className="foc-name">{agent.name}</td>
                  <td>{agent.type}</td>
                  {state === null ? (
                    <>
                      <td className="foc-muted">No telemetry</td>
                      <td className="foc-muted foc-num" colSpan={TELEMETRY_COLUMN_COUNT}>
                        —
                      </td>
                    </>
                  ) : (
                    <>
                      <td>
                        <StatusBadge status={state.status} />
                      </td>
                      <td className="foc-num">{state.lat.toFixed(4)}</td>
                      <td className="foc-num">{state.lng.toFixed(4)}</td>
                      <td className="foc-num">{state.speed.toFixed(1)}</td>
                      <td className="foc-num">{state.battery.toFixed(0)}</td>
                      <td className="foc-time">{new Date(state.recorded_at).toLocaleString()}</td>
                    </>
                  )}
                </tr>
              );
            })
          )}
        </tbody>
      </table>
    </div>
  );
}

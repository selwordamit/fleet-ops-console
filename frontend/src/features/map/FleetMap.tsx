import L from "leaflet";
import { MapContainer, Marker, TileLayer, ZoomControl } from "react-leaflet";

import type { AgentCurrentState, AgentStatus } from "../../types/agent";

// Renders one circular DivIcon marker per agent that has reported telemetry,
// colored by status (Model B palette). Presentational only: receives the
// already-loaded current-state array and selection state, and reports clicks
// back via onSelect. Still REST snapshot mode — markers reflect the load-time
// snapshot, not live updates.
interface FleetMapProps {
  agents: AgentCurrentState[];
  selectedId: number | null;
  onSelect: (id: number) => void;
}

// Build a status-colored circular DivIcon. Color and selected-ring live in the
// .foc-marker CSS (no inline style strings); the wrapper class carries status
// and selection. A DivIcon is an HTML element, so there is no image asset for
// Vite to fail to resolve.
function makeIcon(status: AgentStatus, selected: boolean) {
  const size = selected ? 18 : 13;
  return L.divIcon({
    className: `foc-marker foc-marker--${status}${selected ? " foc-marker--selected" : ""}`,
    html: '<span class="foc-marker__dot"></span>',
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
  });
}

// Tel Aviv area; the fleet operates around central Israel.
const TEL_AVIV_CENTER: [number, number] = [32.0853, 34.7818];
const DEFAULT_ZOOM = 12;

export default function FleetMap({ agents, selectedId, onSelect }: FleetMapProps) {
  // Agents without latest_state have not reported telemetry yet, so they have no
  // coordinate to plot — skip them. This also keeps state.lat/lng access safe.
  const located = agents.filter((agent) => agent.latest_state !== null);

  return (
    <MapContainer
      center={TEL_AVIV_CENTER}
      zoom={DEFAULT_ZOOM}
      scrollWheelZoom
      zoomControl={false}
      className="foc-map__canvas"
    >
      <ZoomControl position="bottomright" />
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      {located.map((agent) => {
        // Narrowed by the filter above; latest_state is non-null here.
        const state = agent.latest_state!;
        return (
          <Marker
            key={agent.id}
            position={[state.lat, state.lng]}
            icon={makeIcon(state.status, agent.id === selectedId)}
            eventHandlers={{ click: () => onSelect(agent.id) }}
          />
        );
      })}
    </MapContainer>
  );
}
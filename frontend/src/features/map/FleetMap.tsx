import { useEffect, useRef } from "react";
import L from "leaflet";
import { MapContainer, Marker, TileLayer, ZoomControl, useMap } from "react-leaflet";
import MarkerClusterGroup from "react-leaflet-cluster";

import type { AgentCurrentState, AgentStatus } from "../../types/agent";

interface FleetMapProps {
  agents: AgentCurrentState[];
  selectedId: number | null;
  onSelect: (id: number) => void;
}


function makeIcon(status: AgentStatus, selected: boolean) {
  const size = selected ? 18 : 13;
  return L.divIcon({
    className: `foc-marker foc-marker--${status}${selected ? " foc-marker--selected" : ""}`,
    html: '<span class="foc-marker__dot"></span>',
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
  });
}

// Must render inside <MapContainer> so useMap() can reach the Leaflet instance.
function MapController({ selectedId, located }: { selectedId: number | null; located: AgentCurrentState[] }) {
  const map = useMap();
  // Tracks the last id we acted on. When telemetry re-renders fire while the
  // same agent is selected, the ref stays equal to selectedId and setView is
  // skipped — the user can freely pan/zoom without the map snapping back.
  const prevSelectedIdRef = useRef<number | null>(null);
  useEffect(() => {
    if (selectedId === null) return;
    if (selectedId === prevSelectedIdRef.current) return;
    const agent = located.find((a) => a.id === selectedId);
    if (!agent?.latest_state) return;
    const { lat, lng } = agent.latest_state;
    // Zoom 18 matches disableClusteringAtZoom so the marker is fully unclustered.
    map.setView([lat, lng], 18, { animate: true });
    prevSelectedIdRef.current = selectedId;
  }, [selectedId, located, map]);
  return null;
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
      <MapController selectedId={selectedId} located={located} />
      <ZoomControl position="bottomright" />
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
        url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
      />
      <MarkerClusterGroup chunkedLoading disableClusteringAtZoom={18} maxClusterRadius={50}>
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
      </MarkerClusterGroup>
    </MapContainer>
  );
}
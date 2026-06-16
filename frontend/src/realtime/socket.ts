// Shared Socket.IO client for the real-time channel.
//
// One instance for the whole app. React controls when it connects
// (autoConnect: false), so importing this module never opens a connection on
// its own. Listeners and connection lifecycle live in the components that use
// this socket, not here.

import { io, type Socket } from "socket.io-client";


const SOCKET_URL = import.meta.env.VITE_SOCKET_URL;

if (!SOCKET_URL) {

  
  throw new Error(
    "VITE_SOCKET_URL is not set. Create frontend/.env.local from " +
      "frontend/.env.example (e.g. VITE_SOCKET_URL=http://localhost:8000).",
  );
}

export const socket: Socket = io(SOCKET_URL, {
  // React opens/closes the connection; module import must have no side effect.
  autoConnect: false,
  // Prefer a WebSocket; fall back to HTTP long-polling where WS is unavailable.
  transports: ["websocket", "polling"],
});

// Shared Socket.IO client for the real-time channel.
//
// One instance for the whole app. React controls when it connects
// (autoConnect: false), so importing this module never opens a connection on
// its own. Listeners and connection lifecycle live in the components that use
// this socket, not here.

import { io, type Socket } from "socket.io-client";

// Backend origin in local development. Hardcoded for the MVP (no env vars yet).
// Socket.IO uses the /socket.io/ path, which the Vite dev proxy does not handle,
// so we target the backend directly instead of a same-origin relative path.
const BACKEND_URL = "http://localhost:8000";

export const socket: Socket = io(BACKEND_URL, {
  // React opens/closes the connection; module import must have no side effect.
  autoConnect: false,
  // Prefer a WebSocket; fall back to HTTP long-polling where WS is unavailable.
  transports: ["websocket", "polling"],
});

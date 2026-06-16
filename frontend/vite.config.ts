import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev server proxies /api to the FastAPI backend (port 8000, routes already
// under the /api prefix), so the client calls same-origin /api/... with no CORS
// setup. Native `npm run dev` reaches the backend on localhost; inside Docker the
// dev server runs in its own container, where localhost has no backend, so the
// target must be the compose service name (set via VITE_PROXY_TARGET).
const proxyTarget = process.env.VITE_PROXY_TARGET ?? "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": {
        target: proxyTarget,
        changeOrigin: true,
      },
    },
  },
});

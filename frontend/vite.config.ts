import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev server proxies /api to the FastAPI backend (port 8000, routes already
// under the /api prefix), so the client calls same-origin /api/... with no CORS
// setup. Absolute backend URLs / env vars are intentionally avoided for the MVP.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});

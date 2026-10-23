import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev server proxies the API paths to the FastAPI backend on :8000, so the app
// uses same-origin relative URLs (same as when FastAPI serves the built assets).
const api = { target: "http://localhost:8000", changeOrigin: true };

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/sessions": api,
      "/environments": api,
      "/refreshes": api,
      "/health": api,
    },
  },
});

import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Dev server proxies API + WebSocket traffic to the FastAPI backend.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5180,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8422",
        changeOrigin: true,
        ws: true,
      },
    },
  },
  build: {
    chunkSizeWarningLimit: 900,
  },
});

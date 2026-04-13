import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Default 24678: on many Windows setups 5173 (and nearby ports) hit EACCES due to Hyper-V / excluded
// TCP ranges. Override with VITE_DEV_SERVER_PORT=5173 when your machine allows it.
const devPort = Number(process.env.VITE_DEV_SERVER_PORT) || 24678;
const apiProxyTarget = process.env.VITE_API_PROXY_TARGET || "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: devPort,
    strictPort: false,
    proxy: {
      "/api": { target: apiProxyTarget, changeOrigin: true, timeout: 600_000 },
      "/metrics": { target: apiProxyTarget, changeOrigin: true },
    },
  },
});

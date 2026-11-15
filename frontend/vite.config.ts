import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// The dev script picks a free port and passes it through, so a stale server
// never breaks `npm run dev`. 8787 keeps Marasa off port 8000.
const backendPort = process.env.MARASA_BACKEND_PORT ?? "8787";

// Marasa is device-local. The Vite dev server therefore binds only to
// loopback and does not accept arbitrary LAN Host headers.
const host = process.env.MARASA_VITE_HOST ?? "127.0.0.1";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host,
    port: Number(process.env.MARASA_FRONTEND_PORT ?? 5173),
    strictPort: false,
    // Keep Vite's DNS-rebinding protection enabled.
    allowedHosts: undefined,
    proxy: {
      "/api": {
        target: `http://127.0.0.1:${backendPort}`,
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: "dist",
    sourcemap: true,
  },
});

import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// The dev script picks a free port and passes it through, so a stale server
// on 8000 never breaks `npm run dev`.
const backendPort = process.env.MARASA_BACKEND_PORT ?? "8000";

// 127.0.0.1 by default; `scripts/dev.ps1 -Expose` sets 0.0.0.0 so phones and
// other devices on the LAN can reach the dev server.
const host = process.env.MARASA_VITE_HOST ?? "127.0.0.1";
const lanMode = host === "0.0.0.0";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host,
    port: Number(process.env.MARASA_FRONTEND_PORT ?? 5173),
    strictPort: false,
    // Vite blocks requests for unknown Host headers (DNS-rebinding protection).
    // On a trusted home network we accept them so a phone can load the app.
    allowedHosts: lanMode ? true : undefined,
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

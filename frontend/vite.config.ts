import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// The dev script picks a free port and passes it through, so a stale server
// on 8000 never breaks `npm run dev`.
const backendPort = process.env.MARASA_BACKEND_PORT ?? "8000";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: "127.0.0.1",
    port: Number(process.env.MARASA_FRONTEND_PORT ?? 5173),
    strictPort: false,
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

import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

// Ports stay overridable so the dashboard and its e2e suite can run alongside an
// already-running local stack (docker compose binds 5173/8000 by default).
const webPort = Number(process.env.SASYAAI_WEB_PORT ?? 5173);
const apiOrigin = `http://127.0.0.1:${process.env.SASYAAI_API_PORT ?? 8000}`;
const apiProxy = { "/api": apiOrigin, "/health": apiOrigin };

export default defineConfig({
  plugins: [react()],
  server: {
    port: webPort,
    proxy: apiProxy,
  },
  preview: {
    port: webPort,
    proxy: apiProxy,
  },
  test: {
    environment: "jsdom",
    setupFiles: "./src/test/setup.ts",
    include: ["src/**/*.test.{ts,tsx}"],
  },
});

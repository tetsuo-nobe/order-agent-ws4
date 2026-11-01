import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Vite 設定（React SPA）
export default defineConfig({
  plugins: [react()],
  server: { port: 5173 },
});

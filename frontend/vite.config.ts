import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// WebApp хостится по пути /app, поэтому assets-URL'ы должны быть относительные к /app/.
// Сам HTML лежит в /srv/app/index.html, JS/CSS в /srv/app/assets/...
export default defineConfig({
  plugins: [react()],
  base: "/app/",
  server: {
    port: 5173,
    host: true,
  },
});

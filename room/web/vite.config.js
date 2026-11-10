import { defineConfig } from 'vite';
export default defineConfig({
  define: { __BUILD__: JSON.stringify(String(Date.now())) },
  base: './',
  build: { target: 'es2020', assetsInlineLimit: 0, chunkSizeWarningLimit: 3000 },
  server: { host: '0.0.0.0', port: 5173 },
});

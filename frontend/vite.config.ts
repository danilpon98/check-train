import { fileURLToPath, URL } from 'node:url'
import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

// Сборка кладётся прямо в python-пакет: FastAPI отдаёт её как статику.
// base='/static/' — ассеты лежат по /static/..., а index.html и /sw.js бэкенд отдаёт из корня.
export default defineConfig({
  plugins: [vue()],
  base: '/static/',
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  build: {
    outDir: '../trainwatch/static',
    emptyOutDir: true,
    target: 'es2022',
  },
  server: {
    port: 5173,
    // режим разработки: API, SSE и service worker — с запущенного бэкенда
    proxy: {
      '/api': { target: 'http://127.0.0.1:8765', changeOrigin: false },
      '/sw.js': { target: 'http://127.0.0.1:8765' },
    },
  },
})

import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      '/threads': { target: 'http://localhost:2024', changeOrigin: true },
      '/store': { target: 'http://localhost:2024', changeOrigin: true },
      '/runs': { target: 'http://localhost:2024', changeOrigin: true },
      '/files': { target: 'http://localhost:2024', changeOrigin: true },
      '/health': { target: 'http://localhost:2024', changeOrigin: true },
      '/webhooks': { target: 'http://localhost:2024', changeOrigin: true },
    },
  },
})

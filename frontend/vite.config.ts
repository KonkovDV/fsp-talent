import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': { target: 'http://localhost:8000', changeOrigin: true },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
    rollupOptions: {
      output: {
        manualChunks(id: string) {
          const path = id.replace(/\\/g, '/')
          if (!path.includes('node_modules')) return
          if (path.includes('@tanstack/react-query')) return 'query'
          if (path.includes('/react-dom/') || path.includes('/react-router') || path.includes('/react/')) return 'vendor'
        },
      },
    },
  },
})

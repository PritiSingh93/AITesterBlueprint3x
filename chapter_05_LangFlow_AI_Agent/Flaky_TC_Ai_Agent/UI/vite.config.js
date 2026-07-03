import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // Proxies calls to the local Langflow server to avoid browser CORS issues.
      '/langflow-api': {
        target: 'http://localhost:7861',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/langflow-api/, ''),
      },
    },
  },
})

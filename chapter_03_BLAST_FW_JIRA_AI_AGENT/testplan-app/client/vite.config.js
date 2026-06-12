import { defineConfig } from 'vite'

// Proxy `/api` during development to the backend server running on port 4000
export default defineConfig({
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:4000',
        changeOrigin: true,
        secure: false
      }
    }
  }
})

import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// The backend runs on port 8000. The proxy turns /api/upload into http://127.0.0.1:8000/upload,
// so the browser never has to deal with CORS.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})

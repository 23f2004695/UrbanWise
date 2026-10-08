import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// The backend port must match PORT in backend/.env (default 5050).
const apiPort = process.env.API_PORT || 5050

export default defineConfig({
  plugins: [vue()],
  server: {
    proxy: {
      '/api': `http://localhost:${apiPort}`,
    },
  },
  test: {
    environment: 'node',
  },
})

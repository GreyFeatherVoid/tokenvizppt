import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 6080,
    proxy: {
      '/api': {
        target: 'http://localhost:6001',
        changeOrigin: true,
      },
    },
  },
})

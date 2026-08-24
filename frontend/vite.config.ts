import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const allowedHostsRaw = process.env.VITE_ALLOWED_HOSTS ?? 'localhost,127.0.0.1'
const allowedHosts = allowedHostsRaw
  .split(',')
  .map((host) => host.trim())
  .filter(Boolean)

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    allowedHosts: allowedHosts.includes('*') ? true : allowedHosts,
    proxy: {
      '/api': {
        target: 'http://backend:8000',
        changeOrigin: true,
      },
    },
  },
})

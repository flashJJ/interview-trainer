import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { '/api': { target: 'http://localhost:8000', changeOrigin: true } },
    // dev server 启动后后台预热入口模块依赖，缩短首次深链访问的白屏时间
    warmup: {
      clientFiles: ['./src/main.tsx'],
    },
  },
})

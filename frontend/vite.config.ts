import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    port: 5173,
    proxy: { '/api': { target: 'http://localhost:8000', changeOrigin: true } },
    // dev server 启动后后台预热入口模块依赖，缩短首次深链访问的白屏时间
    warmup: {
      clientFiles: ['./src/main.tsx'],
    },
  },
  build: {
    // 路由懒加载后单页 chunk 约 200-400KB，调低告警阈值以便观察
    chunkSizeWarningLimit: 800,
    rollupOptions: {
      output: {
        // 第三方库独立分块：echarts 仅分析页需要，首屏不加载；react/antd 可长期缓存
        manualChunks: {
          'vendor-react': ['react', 'react-dom', 'react-router-dom'],
          'vendor-antd': ['antd', '@ant-design/icons'],
          'vendor-echarts': ['echarts', 'echarts-for-react'],
          'vendor-query': ['@tanstack/react-query'],
        },
      },
    },
  },
})

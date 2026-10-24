import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { App as AntdApp, ConfigProvider } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import { QueryClientProvider } from '@tanstack/react-query'
import App from './App'
import { AuthProvider } from './store/auth'
import ErrorBoundary from './components/ErrorBoundary'
import { queryClient } from './app/queryClient'

// 未捕获的 Promise 异常记录（避免静默失败难以定位）
window.addEventListener('unhandledrejection', (event) => {
  console.error('[unhandledrejection]', event.reason)
})

ReactDOM.createRoot(document.getElementById('root')!).render(
  <ConfigProvider locale={zhCN} theme={{ token: { colorPrimary: '#2f54eb' } }}>
    <AntdApp>
      <ErrorBoundary>
        <QueryClientProvider client={queryClient}>
          <BrowserRouter>
            <AuthProvider>
              <App />
            </AuthProvider>
          </BrowserRouter>
        </QueryClientProvider>
      </ErrorBoundary>
    </AntdApp>
  </ConfigProvider>,
)

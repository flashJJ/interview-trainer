import { Component, type ErrorInfo, type ReactNode } from 'react'
import { Button, Result } from 'antd'

interface Props {
  children: ReactNode
}

interface State {
  error: Error | null
}

/**
 * 全局错误边界：页面渲染异常时展示友好错误页而非整树白屏。
 * 与 ErrorBoundary 配套的还有 window 级 unhandledrejection 监听（main.tsx）。
 */
export default class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // 保留完整堆栈到控制台，便于定位（生产可替换为上报服务）
    console.error('[ErrorBoundary]', error, info.componentStack)
  }

  render() {
    if (this.state.error) {
      return (
        <Result
          status="error"
          title="页面渲染出错"
          subTitle={this.state.error.message}
          extra={[
            <Button key="reload" type="primary" onClick={() => window.location.reload()}>
              刷新页面
            </Button>,
            <Button key="home" onClick={() => { window.location.href = '/' }}>
              返回首页
            </Button>,
          ]}
        />
      )
    }
    return this.props.children
  }
}

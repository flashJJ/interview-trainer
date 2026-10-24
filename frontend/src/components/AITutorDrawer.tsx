import { useCallback, useEffect, useRef, useState } from 'react'
import {
  Alert,
  App as AntdApp,
  Button,
  Drawer,
  Empty,
  Input,
  Space,
  Spin,
  Typography,
} from 'antd'
import { RobotOutlined, SendOutlined, UserOutlined } from '@ant-design/icons'
import { chatApi, settingsApi } from '../api/client'
import type { ChatMessage } from '../api/types'

interface AITutorDrawerProps {
  questionId: number | null
  questionTitle?: string
  open: boolean
  onClose: () => void
}

export default function AITutorDrawer({ questionId, questionTitle, open, onClose }: AITutorDrawerProps) {
  const { message } = AntdApp.useApp()
  const [llmEnabled, setLlmEnabled] = useState<boolean | null>(null)
  const [sessionId, setSessionId] = useState<number | null>(null)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [loadingHistory, setLoadingHistory] = useState(false)
  const [sending, setSending] = useState(false)
  const [input, setInput] = useState('')
  const listRef = useRef<HTMLDivElement>(null)

  // 打开时：检查 LLM 配置 -> 找/建会话 -> 加载历史
  const initSession = useCallback(async () => {
    if (questionId == null) return
    setLoadingHistory(true)
    try {
      const cfg = await settingsApi.get()
      setLlmEnabled(cfg.llm_enabled)
      if (!cfg.llm_enabled) return
      const sessions = await chatApi.listSessions(questionId)
      const session = sessions[0] ?? (await chatApi.createSession(questionId))
      setSessionId(session.id)
      const history = await chatApi.listMessages(session.id)
      setMessages(history)
    } catch (err) {
      message.error(err instanceof Error ? err.message : '初始化讲题会话失败')
    } finally {
      setLoadingHistory(false)
    }
  }, [questionId, message])

  useEffect(() => {
    if (open) {
      setMessages([])
      setSessionId(null)
      void initSession()
    }
  }, [open, initSession])

  // 新消息时滚动到底部
  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages])

  const onSend = async () => {
    const content = input.trim()
    if (!content || sessionId == null || sending) return
    setInput('')
    setMessages((prev) => [
      ...prev,
      { id: Date.now(), role: 'user', content, created_at: new Date().toISOString() },
    ])
    setSending(true)
    let streamed = ''
    try {
      await chatApi.sendMessageStream(sessionId, content, {
        onChunk: (text) => {
          streamed += text
          setMessages((prev) => {
            const last = prev[prev.length - 1]
            if (last && last.role === 'assistant' && last.id < 0) {
              return [...prev.slice(0, -1), { ...last, content: last.content + text }]
            }
            return [...prev, { id: -Date.now(), role: 'assistant', content: text, created_at: new Date().toISOString() }]
          })
        },
        onDone: () => {
          setSending(false)
        },
        onError: (errMsg) => {
          setSending(false)
          message.error(errMsg)
        },
      })
    } catch (err) {
      setSending(false)
      message.error(err instanceof Error ? err.message : '发送失败')
    }
  }

  return (
    <Drawer
      title={
        <Space>
          <RobotOutlined />
          <span>AI 讲题</span>
          {questionTitle && (
            <Typography.Text type="secondary" ellipsis style={{ maxWidth: 260, fontSize: 12 }}>
              {questionTitle}
            </Typography.Text>
          )}
        </Space>
      }
      open={open}
      onClose={onClose}
      width={480}
      destroyOnHidden
    >
      {llmEnabled === false && (
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
          message="AI 讲题需要配置 LLM"
          description="请前往「系统配置」填写 Base URL 与 API Key（支持任意 OpenAI 兼容服务），保存后即可使用。"
        />
      )}

      {loadingHistory ? (
        <div style={{ textAlign: 'center', padding: 60 }}>
          <Spin tip="正在加载讲题记录…">
            <div style={{ padding: 40 }} />
          </Spin>
        </div>
      ) : messages.length === 0 ? (
        <Empty
          style={{ marginTop: 60 }}
          description="还没有对话记录，问出你的第一个问题吧"
        />
      ) : (
        <div
          ref={listRef}
          style={{ maxHeight: 'calc(100vh - 260px)', overflowY: 'auto', paddingRight: 4 }}
        >
          {messages.map((msg) => (
            <div
              key={msg.id}
              style={{
                display: 'flex',
                justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start',
                marginBottom: 12,
              }}
            >
              <div
                style={{
                  maxWidth: '85%',
                  padding: '8px 12px',
                  borderRadius: 8,
                  background: msg.role === 'user' ? '#2f54eb' : '#f5f5f5',
                  color: msg.role === 'user' ? '#fff' : 'inherit',
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-word',
                  fontSize: 14,
                  lineHeight: 1.6,
                }}
              >
                <Space size={6} style={{ marginBottom: 4 }}>
                  {msg.role === 'user' ? <UserOutlined /> : <RobotOutlined />}
                  <Typography.Text style={{ fontSize: 12, color: msg.role === 'user' ? '#ffffffb3' : '#00000073' }}>
                    {msg.role === 'user' ? '我' : 'AI 老师'}
                  </Typography.Text>
                </Space>
                <div>{msg.content}</div>
              </div>
            </div>
          ))}
        </div>
      )}

      <div style={{ marginTop: 16, borderTop: '1px solid #f0f0f0', paddingTop: 12 }}>
        <Space.Compact style={{ width: '100%' }}>
          <Input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onPressEnter={() => void onSend()}
            placeholder={llmEnabled === false ? '请先配置 LLM' : '输入问题，例如：为什么选 A？'}
            disabled={!llmEnabled || sending || sessionId == null}
            maxLength={2000}
          />
          <Button
            type="primary"
            icon={<SendOutlined />}
            loading={sending}
            disabled={!llmEnabled || !input.trim() || sessionId == null}
            onClick={() => void onSend()}
          >
            发送
          </Button>
        </Space.Compact>
      </div>
    </Drawer>
  )
}

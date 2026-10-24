import { TOKEN_KEY } from './http'
import { errMsg, http } from './http'
import type { ChatMessage, ChatSession } from './types'

export const chatApi = {
  async listSessions(questionId: number): Promise<ChatSession[]> {
    try {
      const { data } = await http.get<ChatSession[]>('/chat/sessions', {
        params: { question_id: questionId },
      })
      return data
    } catch (err) {
      throw new Error(errMsg(err, '获取讲题会话失败'))
    }
  },
  async createSession(questionId: number): Promise<ChatSession> {
    try {
      const { data } = await http.post<ChatSession>('/chat/sessions', { question_id: questionId })
      return data
    } catch (err) {
      throw new Error(errMsg(err, '创建讲题会话失败'))
    }
  },
  async listMessages(sessionId: number): Promise<ChatMessage[]> {
    try {
      const { data } = await http.get<ChatMessage[]>(`/chat/sessions/${sessionId}/messages`)
      return data
    } catch (err) {
      throw new Error(errMsg(err, '获取讲题记录失败'))
    }
  },
  /**
   * 发送消息并以 SSE 流式读取讲解内容。
   * 注意：fetch 不走 axios 拦截器，需手动带 Authorization。
   */
  async sendMessageStream(
    sessionId: number,
    content: string,
    handlers: {
      onChunk: (text: string) => void
      onDone?: () => void
      onError?: (message: string) => void
    },
  ): Promise<void> {
    const token = localStorage.getItem(TOKEN_KEY)
    const resp = await fetch(`/api/chat/sessions/${sessionId}/messages`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({ content }),
    })
    if (!resp.ok) {
      let detail = `请求失败（${resp.status}）`
      try {
        const body = await resp.json()
        detail = body.detail ?? detail
      } catch {
        /* 非 JSON 响应 */
      }
      handlers.onError?.(detail)
      return
    }
    const reader = resp.body?.getReader()
    if (!reader) {
      handlers.onError?.('浏览器不支持流式读取')
      return
    }
    const decoder = new TextDecoder()
    let buffer = ''
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() ?? ''
      for (const line of lines) {
        if (!line.startsWith('data:')) continue
        try {
          const event = JSON.parse(line.slice(5))
          if (event.type === 'chunk') handlers.onChunk(event.content ?? '')
          else if (event.type === 'done') handlers.onDone?.()
          else if (event.type === 'error') handlers.onError?.(event.message ?? '讲解失败')
        } catch {
          /* 半行 JSON，等待下一块 */
        }
      }
    }
    handlers.onDone?.()
  },
}

import axios, { AxiosError } from 'axios'
import type {
  Difficulty,
  ExamPaperDetail,
  ExamPaper,
  ExamQuestion,
  GenerateQuestionsReq,
  GenerateQuestionsResp,
  KnowledgeEntry,
  KnowledgeEntryDetail,
  KnowledgeOverview,
  LoginResp,
  PageResp,
  PracticeByTypeResp,
  PracticeOverview,
  PracticeRecentResp,
  PracticeTrendResp,
  QType,
  Question,
  QuestionAccuracyResp,
  QuestionStatsOverview,
  QuestionsAnalyticsOverview,
  SearchResp,
  SessionDetailResp,
  SessionListItem,
  StartExamResp,
  SubmitExamReq,
  SubmitExamResp,
  SystemConfig,
  SystemConfigIn,
  TestConnectionResult,
  User,
  WrongQuestionItem,
  WrongQuestionStats,
} from './types'

const TOKEN_KEY = 'it_token'

const client = axios.create({
  baseURL: '/api',
  timeout: 60000,
})

client.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY)
  if (token) {
    config.headers = config.headers ?? {}
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

client.interceptors.response.use(
  (resp) => resp,
  (error: AxiosError<{ detail?: string }>) => {
    if (error.response?.status === 401) {
      localStorage.removeItem(TOKEN_KEY)
      localStorage.removeItem('it_user')
      if (window.location.pathname !== '/login') {
        window.location.assign('/login')
      }
    }
    return Promise.reject(error)
  },
)

function errMsg(err: unknown, fallback = '操作失败'): string {
  const e = err as AxiosError<{ detail?: string }>
  return e?.response?.data?.detail ?? fallback
}

// ===== auth =====

export const authApi = {
  async login(username: string, password: string): Promise<LoginResp> {
    try {
      const { data } = await client.post<LoginResp>('/auth/login', { username, password })
      return data
    } catch (err) {
      throw new Error(errMsg(err, '登录失败'))
    }
  },
  async register(username: string, password: string, email?: string): Promise<User> {
    try {
      const { data } = await client.post<User>('/auth/register', { username, password, email })
      return data
    } catch (err) {
      throw new Error(errMsg(err, '注册失败'))
    }
  },
  async me(): Promise<User> {
    try {
      const { data } = await client.get<User>('/auth/me')
      return data
    } catch (err) {
      throw new Error(errMsg(err, '获取用户信息失败'))
    }
  },
}

// ===== knowledge =====

export const knowledgeApi = {
  async listEntries(params: {
    page?: number
    size?: number
    status?: string
    keyword?: string
  }): Promise<PageResp<KnowledgeEntry>> {
    try {
      const { data } = await client.get<PageResp<KnowledgeEntry>>('/knowledge/entries', { params })
      return data
    } catch (err) {
      throw new Error(errMsg(err, '获取知识库列表失败'))
    }
  },
  async createEntry(title: string, content: string): Promise<KnowledgeEntry> {
    try {
      const { data } = await client.post<KnowledgeEntry>('/knowledge/entries', { title, content })
      return data
    } catch (err) {
      throw new Error(errMsg(err, '创建条目失败'))
    }
  },
  async createFromUrl(url: string, title?: string): Promise<KnowledgeEntry> {
    try {
      const { data } = await client.post<KnowledgeEntry>('/knowledge/entries/url', {
        url,
        title: title ?? '',
      })
      return data
    } catch (err) {
      throw new Error(errMsg(err, '链接录入失败'))
    }
  },
  async uploadEntry(file: File, title?: string): Promise<KnowledgeEntry> {
    try {
      const form = new FormData()
      form.append('file', file)
      if (title) form.append('title', title)
      const { data } = await client.post<KnowledgeEntry>('/knowledge/entries/upload', form)
      return data
    } catch (err) {
      throw new Error(errMsg(err, '上传文件失败'))
    }
  },
  async getEntry(id: number): Promise<KnowledgeEntryDetail> {
    try {
      const { data } = await client.get<KnowledgeEntryDetail>(`/knowledge/entries/${id}`)
      return data
    } catch (err) {
      throw new Error(errMsg(err, '获取条目详情失败'))
    }
  },
  async reprocess(id: number): Promise<KnowledgeEntry> {
    try {
      const { data } = await client.post<KnowledgeEntry>(`/knowledge/entries/${id}/reprocess`)
      return data
    } catch (err) {
      throw new Error(errMsg(err, '重新处理失败'))
    }
  },
  async deleteEntry(id: number): Promise<void> {
    try {
      await client.delete(`/knowledge/entries/${id}`)
    } catch (err) {
      throw new Error(errMsg(err, '删除失败'))
    }
  },
  async search(query: string, topK = 5): Promise<SearchResp> {
    try {
      const { data } = await client.post<SearchResp>('/knowledge/search', { query, top_k: topK })
      return data
    } catch (err) {
      throw new Error(errMsg(err, '检索失败'))
    }
  },
  async overview(): Promise<KnowledgeOverview> {
    try {
      const { data } = await client.get<KnowledgeOverview>('/knowledge/stats/overview')
      return data
    } catch (err) {
      throw new Error(errMsg(err, '获取统计失败'))
    }
  },
}

// ===== questions =====

export const questionApi = {
  async list(params: {
    page?: number
    size?: number
    q_type?: QType | ''
    difficulty?: Difficulty | ''
    entry_id?: number
    keyword?: string
    review_status?: 'approved' | 'pending' | 'rejected' | 'all'
  }): Promise<PageResp<Question>> {
    try {
      const { data } = await client.get<PageResp<Question>>('/questions', { params })
      return data
    } catch (err) {
      throw new Error(errMsg(err, '获取题库列表失败'))
    }
  },
  async get(id: number): Promise<Question> {
    try {
      const { data } = await client.get<Question>(`/questions/${id}`)
      return data
    } catch (err) {
      throw new Error(errMsg(err, '获取题目详情失败'))
    }
  },
  async remove(id: number): Promise<void> {
    try {
      await client.delete(`/questions/${id}`)
    } catch (err) {
      throw new Error(errMsg(err, '删除题目失败'))
    }
  },
  async update(
    id: number,
    payload: {
      content?: string
      options?: string[]
      answer?: string
      explanation?: string
      difficulty?: Difficulty
    },
  ): Promise<Question> {
    try {
      const { data } = await client.put<Question>(`/questions/${id}`, payload)
      return data
    } catch (err) {
      throw new Error(errMsg(err, '保存题目失败'))
    }
  },
  async review(id: number, action: 'approve' | 'reject'): Promise<Question> {
    try {
      const { data } = await client.post<Question>(`/questions/${id}/review`, { action })
      return data
    } catch (err) {
      throw new Error(errMsg(err, '审核操作失败'))
    }
  },
  async batchReview(
    questionIds: number[],
    action: 'approve' | 'reject',
  ): Promise<{ ok: boolean; updated: number; message: string }> {
    try {
      const { data } = await client.post<{ ok: boolean; updated: number; message: string }>(
        '/questions/review/batch',
        { question_ids: questionIds, action },
      )
      return data
    } catch (err) {
      throw new Error(errMsg(err, '批量审核失败'))
    }
  },
  async generate(req: GenerateQuestionsReq): Promise<GenerateQuestionsResp> {
    try {
      const { data } = await client.post<GenerateQuestionsResp>('/questions/generate', req)
      return data
    } catch (err) {
      throw new Error(errMsg(err, '生成题目失败'))
    }
  },
  async statsOverview(): Promise<QuestionStatsOverview> {
    try {
      const { data } = await client.get<QuestionStatsOverview>('/questions/stats/overview')
      return data
    } catch (err) {
      throw new Error(errMsg(err, '获取题库统计失败'))
    }
  },
}

// ===== exams =====

export const examApi = {
  async generate(params: {
    title?: string
    count: number
    types: QType[]
    difficulty?: Difficulty | ''
  }): Promise<ExamPaper> {
    try {
      const { data } = await client.post<ExamPaper>('/exams/generate', params)
      return data
    } catch (err) {
      throw new Error(errMsg(err, '生成考卷失败'))
    }
  },
  async list(page = 1, size = 20): Promise<PageResp<ExamPaper>> {
    try {
      const { data } = await client.get<PageResp<ExamPaper>>('/exams', { params: { page, size } })
      return data
    } catch (err) {
      throw new Error(errMsg(err, '获取考卷列表失败'))
    }
  },
  async getPaper(id: number): Promise<ExamPaperDetail> {
    try {
      const { data } = await client.get<ExamPaperDetail>(`/exams/${id}`)
      return data
    } catch (err) {
      throw new Error(errMsg(err, '获取考卷详情失败'))
    }
  },
  async start(paperId: number): Promise<StartExamResp> {
    try {
      const { data } = await client.post<StartExamResp>(`/exams/${paperId}/start`)
      return data
    } catch (err) {
      throw new Error(errMsg(err, '开始考试失败'))
    }
  },
  async submit(sessionId: number, answers: SubmitExamReq['answers']): Promise<SubmitExamResp> {
    try {
      const { data } = await client.post<SubmitExamResp>(
        `/exams/sessions/${sessionId}/submit`,
        { answers },
      )
      return data
    } catch (err) {
      throw new Error(errMsg(err, '提交答卷失败'))
    }
  },
  async save(
    sessionId: number,
    answers: SubmitExamReq['answers'],
  ): Promise<{ ok: boolean; saved: number }> {
    const { data } = await client.post<{ ok: boolean; saved: number }>(
      `/exams/sessions/${sessionId}/save`,
      { answers },
    )
    return data
  },
  async getSession(sessionId: number): Promise<SessionDetailResp> {
    try {
      const { data } = await client.get<SessionDetailResp>(`/exams/sessions/${sessionId}`)
      return data
    } catch (err) {
      throw new Error(errMsg(err, '获取成绩详情失败'))
    }
  },
  async listSessions(page = 1, size = 20): Promise<PageResp<SessionListItem>> {
    try {
      const { data } = await client.get<PageResp<SessionListItem>>('/exams/sessions', {
        params: { page, size },
      })
      return data
    } catch (err) {
      throw new Error(errMsg(err, '获取考试历史失败'))
    }
  },
}

// ===== analytics =====

export const analyticsApi = {
  async questionsOverview(): Promise<QuestionsAnalyticsOverview> {
    try {
      const { data } =
        await client.get<QuestionsAnalyticsOverview>('/analytics/questions/overview')
      return data
    } catch (err) {
      throw new Error(errMsg(err, '获取题目分析数据失败'))
    }
  },
  async questionsAccuracy(limit = 10): Promise<QuestionAccuracyResp> {
    try {
      const { data } = await client.get<QuestionAccuracyResp>('/analytics/questions/accuracy', {
        params: { limit },
      })
      return data
    } catch (err) {
      throw new Error(errMsg(err, '获取正确率数据失败'))
    }
  },
  async practiceOverview(): Promise<PracticeOverview> {
    try {
      const { data } = await client.get<PracticeOverview>('/analytics/practice/overview')
      return data
    } catch (err) {
      throw new Error(errMsg(err, '获取做题分析数据失败'))
    }
  },
  async practiceTrend(days = 30): Promise<PracticeTrendResp> {
    try {
      const { data } = await client.get<PracticeTrendResp>('/analytics/practice/trend', {
        params: { days },
      })
      return data
    } catch (err) {
      throw new Error(errMsg(err, '获取趋势数据失败'))
    }
  },
  async practiceByType(): Promise<PracticeByTypeResp> {
    try {
      const { data } = await client.get<PracticeByTypeResp>('/analytics/practice/by-type')
      return data
    } catch (err) {
      throw new Error(errMsg(err, '获取题型数据失败'))
    }
  },
  async practiceRecent(limit = 10): Promise<PracticeRecentResp> {
    try {
      const { data } = await client.get<PracticeRecentResp>('/analytics/practice/recent', {
        params: { limit },
      })
      return data
    } catch (err) {
      throw new Error(errMsg(err, '获取最近考试失败'))
    }
  },
}

// ===== settings =====

export const settingsApi = {
  async get(): Promise<SystemConfig> {
    try {
      const { data } = await client.get<SystemConfig>('/settings')
      return data
    } catch (err) {
      throw new Error(errMsg(err, '获取系统配置失败'))
    }
  },
  async save(payload: SystemConfigIn): Promise<SystemConfig> {
    try {
      const { data } = await client.put<SystemConfig>('/settings', payload)
      return data
    } catch (err) {
      throw new Error(errMsg(err, '保存配置失败'))
    }
  },
  async reset(): Promise<SystemConfig> {
    try {
      const { data } = await client.post<SystemConfig>('/settings/reset')
      return data
    } catch (err) {
      throw new Error(errMsg(err, '恢复默认失败'))
    }
  },
  async test(payload: {
    target: 'llm' | 'embedding'
    llm_base_url?: string
    llm_api_key?: string
    llm_model?: string
    embedding_base_url?: string
    embedding_api_key?: string
    embedding_model?: string
  }): Promise<TestConnectionResult> {
    try {
      const { data } = await client.post<TestConnectionResult>('/settings/test', payload)
      return data
    } catch (err) {
      throw new Error(errMsg(err, '测试连接失败'))
    }
  },
  async changePassword(oldPassword: string, newPassword: string): Promise<{ ok: boolean; message: string }> {
    try {
      const { data } = await client.post<{ ok: boolean; message: string }>('/settings/password', {
        old_password: oldPassword,
        new_password: newPassword,
      })
      return data
    } catch (err) {
      throw new Error(errMsg(err, '修改密码失败'))
    }
  },
}

// ===== wrong questions（错题本）=====

export const wrongQuestionsApi = {
  async list(params: {
    page?: number
    size?: number
    q_type?: QType | ''
    only_due?: boolean
  }): Promise<PageResp<WrongQuestionItem>> {
    try {
      const { data } = await client.get<PageResp<WrongQuestionItem>>('/wrong-questions', { params })
      return data
    } catch (err) {
      throw new Error(errMsg(err, '获取错题本失败'))
    }
  },
  async stats(): Promise<WrongQuestionStats> {
    try {
      const { data } = await client.get<WrongQuestionStats>('/wrong-questions/stats')
      return data
    } catch (err) {
      throw new Error(errMsg(err, '获取错题统计失败'))
    }
  },
  async generateReview(count = 10): Promise<ExamPaper> {
    try {
      const { data } = await client.post<ExamPaper>('/wrong-questions/review/generate', { count })
      return data
    } catch (err) {
      throw new Error(errMsg(err, '生成复习卷失败'))
    }
  },
  async master(id: number): Promise<void> {
    try {
      await client.post(`/wrong-questions/${id}/master`)
    } catch (err) {
      throw new Error(errMsg(err, '操作失败'))
    }
  },
  async remove(id: number): Promise<void> {
    try {
      await client.delete(`/wrong-questions/${id}`)
    } catch (err) {
      throw new Error(errMsg(err, '移除失败'))
    }
  },
}

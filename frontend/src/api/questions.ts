import { errMsg, http } from './http'
import type {
  Difficulty,
  GenerateQuestionsReq,
  GenerateQuestionsResp,
  PageResp,
  QType,
  Question,
  QuestionSource,
  QuestionStatsOverview,
} from './types'

export const questionApi = {
  async list(params: {
    page?: number
    size?: number
    q_type?: QType | ''
    difficulty?: Difficulty | ''
    entry_id?: number
    keyword?: string
    source?: QuestionSource | ''
    review_status?: 'approved' | 'pending' | 'rejected' | 'all'
  }): Promise<PageResp<Question>> {
    try {
      const { data } = await http.get<PageResp<Question>>('/questions', { params })
      return data
    } catch (err) {
      throw new Error(errMsg(err, '获取题库列表失败'))
    }
  },
  async get(id: number): Promise<Question> {
    try {
      const { data } = await http.get<Question>(`/questions/${id}`)
      return data
    } catch (err) {
      throw new Error(errMsg(err, '获取题目详情失败'))
    }
  },
  async remove(id: number): Promise<void> {
    try {
      await http.delete(`/questions/${id}`)
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
      const { data } = await http.put<Question>(`/questions/${id}`, payload)
      return data
    } catch (err) {
      throw new Error(errMsg(err, '保存题目失败'))
    }
  },
  async review(id: number, action: 'approve' | 'reject'): Promise<Question> {
    try {
      const { data } = await http.post<Question>(`/questions/${id}/review`, { action })
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
      const { data } = await http.post<{ ok: boolean; updated: number; message: string }>(
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
      // 出题走 LLM 时为多发并发调用，耗时可达 1-3 分钟，单独放宽超时（全局默认 60s）
      const { data } = await http.post<GenerateQuestionsResp>('/questions/generate', req, {
        timeout: 300_000,
      })
      return data
    } catch (err) {
      throw new Error(errMsg(err, '生成题目失败'))
    }
  },
  async statsOverview(): Promise<QuestionStatsOverview> {
    try {
      const { data } = await http.get<QuestionStatsOverview>('/questions/stats/overview')
      return data
    } catch (err) {
      throw new Error(errMsg(err, '获取题库统计失败'))
    }
  },
}

import { errMsg, http } from './http'
import type { ExamPaper, PageResp, QType, WrongQuestionItem, WrongQuestionStats } from './types'

export const wrongQuestionsApi = {
  async list(params: {
    page?: number
    size?: number
    q_type?: QType | ''
    only_due?: boolean
  }): Promise<PageResp<WrongQuestionItem>> {
    try {
      const { data } = await http.get<PageResp<WrongQuestionItem>>('/wrong-questions', { params })
      return data
    } catch (err) {
      throw new Error(errMsg(err, '获取错题本失败'))
    }
  },
  async stats(): Promise<WrongQuestionStats> {
    try {
      const { data } = await http.get<WrongQuestionStats>('/wrong-questions/stats')
      return data
    } catch (err) {
      throw new Error(errMsg(err, '获取错题统计失败'))
    }
  },
  async generateReview(count = 10): Promise<ExamPaper> {
    try {
      const { data } = await http.post<ExamPaper>('/wrong-questions/review/generate', { count })
      return data
    } catch (err) {
      throw new Error(errMsg(err, '生成复习卷失败'))
    }
  },
  async master(id: number): Promise<void> {
    try {
      await http.post(`/wrong-questions/${id}/master`)
    } catch (err) {
      throw new Error(errMsg(err, '操作失败'))
    }
  },
  async remove(id: number): Promise<void> {
    try {
      await http.delete(`/wrong-questions/${id}`)
    } catch (err) {
      throw new Error(errMsg(err, '移除失败'))
    }
  },
}

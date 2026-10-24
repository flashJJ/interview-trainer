import { errMsg, http } from './http'
import type {
  PracticeByTypeResp,
  PracticeOverview,
  PracticeRecentResp,
  PracticeTrendResp,
  QuestionAccuracyResp,
  QuestionsAnalyticsOverview,
} from './types'

export const analyticsApi = {
  async questionsOverview(): Promise<QuestionsAnalyticsOverview> {
    try {
      const { data } = await http.get<QuestionsAnalyticsOverview>('/analytics/questions/overview')
      return data
    } catch (err) {
      throw new Error(errMsg(err, '获取题目分析数据失败'))
    }
  },
  async questionsAccuracy(limit = 10): Promise<QuestionAccuracyResp> {
    try {
      const { data } = await http.get<QuestionAccuracyResp>('/analytics/questions/accuracy', {
        params: { limit },
      })
      return data
    } catch (err) {
      throw new Error(errMsg(err, '获取正确率数据失败'))
    }
  },
  async practiceOverview(): Promise<PracticeOverview> {
    try {
      const { data } = await http.get<PracticeOverview>('/analytics/practice/overview')
      return data
    } catch (err) {
      throw new Error(errMsg(err, '获取做题分析数据失败'))
    }
  },
  async practiceTrend(days = 30): Promise<PracticeTrendResp> {
    try {
      const { data } = await http.get<PracticeTrendResp>('/analytics/practice/trend', {
        params: { days },
      })
      return data
    } catch (err) {
      throw new Error(errMsg(err, '获取趋势数据失败'))
    }
  },
  async practiceByType(): Promise<PracticeByTypeResp> {
    try {
      const { data } = await http.get<PracticeByTypeResp>('/analytics/practice/by-type')
      return data
    } catch (err) {
      throw new Error(errMsg(err, '获取题型数据失败'))
    }
  },
  async practiceRecent(limit = 10): Promise<PracticeRecentResp> {
    try {
      const { data } = await http.get<PracticeRecentResp>('/analytics/practice/recent', {
        params: { limit },
      })
      return data
    } catch (err) {
      throw new Error(errMsg(err, '获取最近考试失败'))
    }
  },
}

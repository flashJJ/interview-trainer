import { errMsg, http } from './http'
import type {
  ExamPaper,
  MasteryDim,
  MasteryDimension,
  MasteryOverview,
  MasteryRadar,
  MasteryWeak,
  QType,
} from './types'

export const masteryApi = {
  async overview(threshold = 0.6): Promise<MasteryOverview> {
    try {
      const { data } = await http.get<MasteryOverview>('/mastery/overview', {
        params: { threshold },
      })
      return data
    } catch (err) {
      throw new Error(errMsg(err, '获取掌握度概览失败'))
    }
  },

  async dimensions(dim: MasteryDim): Promise<MasteryDimension> {
    try {
      const { data } = await http.get<MasteryDimension>('/mastery/dimensions', {
        params: { dim },
      })
      return data
    } catch (err) {
      throw new Error(errMsg(err, '获取维度掌握度失败'))
    }
  },

  async radar(): Promise<MasteryRadar> {
    try {
      const { data } = await http.get<MasteryRadar>('/mastery/radar')
      return data
    } catch (err) {
      throw new Error(errMsg(err, '获取掌握度雷达失败'))
    }
  },

  async weakPoints(threshold = 0.6, limit = 5): Promise<MasteryWeak> {
    try {
      const { data } = await http.get<MasteryWeak>('/mastery/weak-points', {
        params: { threshold, limit },
      })
      return data
    } catch (err) {
      throw new Error(errMsg(err, '获取薄弱项失败'))
    }
  },

  /** 从薄弱维度一键组卷，返回考卷（调用方跳转到 /exam/{id} 开考）。 */
  async targetedExam(payload: {
    dim: MasteryDim
    key: string
    count: number
    types: QType[]
    title?: string
  }): Promise<ExamPaper> {
    try {
      const { data } = await http.post<ExamPaper>('/exams/targeted', payload)
      return data
    } catch (err) {
      throw new Error(errMsg(err, '生成针对性练习失败'))
    }
  },
}

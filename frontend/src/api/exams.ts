import { errMsg, http } from './http'
import type {
  ExamPaper,
  ExamPaperDetail,
  PageResp,
  QType,
  SessionDetailResp,
  SessionListItem,
  StartExamResp,
  SubmitExamReq,
  SubmitExamResp,
} from './types'

export const examApi = {
  async generate(params: {
    title?: string
    count: number
    types: QType[]
    difficulty?: string
  }): Promise<ExamPaper> {
    try {
      const { data } = await http.post<ExamPaper>('/exams/generate', params)
      return data
    } catch (err) {
      throw new Error(errMsg(err, '生成考卷失败'))
    }
  },
  async list(page = 1, size = 20): Promise<PageResp<ExamPaper>> {
    try {
      const { data } = await http.get<PageResp<ExamPaper>>('/exams', { params: { page, size } })
      return data
    } catch (err) {
      throw new Error(errMsg(err, '获取考卷列表失败'))
    }
  },
  async getPaper(id: number): Promise<ExamPaperDetail> {
    try {
      const { data } = await http.get<ExamPaperDetail>(`/exams/${id}`)
      return data
    } catch (err) {
      throw new Error(errMsg(err, '获取考卷详情失败'))
    }
  },
  async start(paperId: number): Promise<StartExamResp> {
    try {
      const { data } = await http.post<StartExamResp>(`/exams/${paperId}/start`)
      return data
    } catch (err) {
      throw new Error(errMsg(err, '开始考试失败'))
    }
  },
  async submit(sessionId: number, answers: SubmitExamReq['answers']): Promise<SubmitExamResp> {
    try {
      const { data } = await http.post<SubmitExamResp>(`/exams/sessions/${sessionId}/submit`, {
        answers,
      })
      return data
    } catch (err) {
      throw new Error(errMsg(err, '提交答卷失败'))
    }
  },
  async save(
    sessionId: number,
    answers: SubmitExamReq['answers'],
  ): Promise<{ ok: boolean; saved: number }> {
    const { data } = await http.post<{ ok: boolean; saved: number }>(
      `/exams/sessions/${sessionId}/save`,
      { answers },
    )
    return data
  },
  async getSession(sessionId: number): Promise<SessionDetailResp> {
    try {
      const { data } = await http.get<SessionDetailResp>(`/exams/sessions/${sessionId}`)
      return data
    } catch (err) {
      throw new Error(errMsg(err, '获取成绩详情失败'))
    }
  },
  async listSessions(page = 1, size = 20): Promise<PageResp<SessionListItem>> {
    try {
      const { data } = await http.get<PageResp<SessionListItem>>('/exams/sessions', {
        params: { page, size },
      })
      return data
    } catch (err) {
      throw new Error(errMsg(err, '获取考试历史失败'))
    }
  },
}

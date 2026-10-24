import { errMsg, http } from './http'
import type { ChunkPickerItem, EvalCase, EvalOverview, EvalRun, EvalRunBrief } from './types'

/** 评测集自动生成要逐块调用 LLM（实测 16~40s/条，服务端并发 6），客户端需长超时 */
const AUTO_BUILD_TIMEOUT = 900_000
/** 评测本身是本地计算，但用例多时也要几秒到几十秒 */
const RUN_TIMEOUT = 600_000

export const retrievalApi = {
  async overview(): Promise<EvalOverview> {
    try {
      const { data } = await http.get<EvalOverview>('/retrieval/overview')
      return data
    } catch (err) {
      throw new Error(errMsg(err, '获取检索评测概览失败'))
    }
  },

  async listCases(): Promise<EvalCase[]> {
    try {
      const { data } = await http.get<EvalCase[]>('/retrieval/cases')
      return data
    } catch (err) {
      throw new Error(errMsg(err, '获取评测集失败'))
    }
  },

  async createCase(payload: {
    query: string
    expected_ids: number[]
    note?: string
  }): Promise<EvalCase> {
    try {
      const { data } = await http.post<EvalCase>('/retrieval/cases', payload)
      return data
    } catch (err) {
      throw new Error(errMsg(err, '新增评测用例失败'))
    }
  },

  async deleteCase(id: number): Promise<void> {
    try {
      await http.delete(`/retrieval/cases/${id}`)
    } catch (err) {
      throw new Error(errMsg(err, '删除评测用例失败'))
    }
  },

  async clearCases(): Promise<{ deleted: number }> {
    try {
      const { data } = await http.delete<{ deleted: number }>('/retrieval/cases')
      return data
    } catch (err) {
      throw new Error(errMsg(err, '清空评测集失败'))
    }
  },

  async autoBuild(
    count: number,
    useLlm: boolean,
  ): Promise<{ created: number; skipped: number; total_cases: number }> {
    try {
      const { data } = await http.post<{ created: number; skipped: number; total_cases: number }>(
        '/retrieval/cases/auto',
        { count, use_llm: useLlm },
        { timeout: AUTO_BUILD_TIMEOUT },
      )
      return data
    } catch (err) {
      throw new Error(errMsg(err, '自动生成评测集失败'))
    }
  },

  async run(payload: {
    top_k: number
    use_rewrite: boolean
    include_llm_rewrite?: boolean
    vector_weight: number
  }): Promise<EvalRun> {
    try {
      const { data } = await http.post<EvalRun>('/retrieval/run', payload, { timeout: RUN_TIMEOUT })
      return data
    } catch (err) {
      throw new Error(errMsg(err, '运行评测失败'))
    }
  },

  async listRuns(limit = 10): Promise<EvalRunBrief[]> {
    try {
      const { data } = await http.get<EvalRunBrief[]>('/retrieval/runs', { params: { limit } })
      return data
    } catch (err) {
      throw new Error(errMsg(err, '获取评测历史失败'))
    }
  },

  async getRun(id: number): Promise<EvalRun> {
    try {
      const { data } = await http.get<EvalRun>(`/retrieval/runs/${id}`)
      return data
    } catch (err) {
      throw new Error(errMsg(err, '获取评测明细失败'))
    }
  },

  async listChunks(keyword = ''): Promise<ChunkPickerItem[]> {
    try {
      const { data } = await http.get<ChunkPickerItem[]>('/retrieval/chunks', {
        params: { keyword },
      })
      return data
    } catch (err) {
      throw new Error(errMsg(err, '获取知识块失败'))
    }
  },
}

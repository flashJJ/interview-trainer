import { errMsg, http } from './http'
import type {
  KnowledgeEntry,
  KnowledgeEntryDetail,
  KnowledgeOverview,
  PageResp,
  SearchResp,
} from './types'

export const knowledgeApi = {
  async listEntries(params: {
    page?: number
    size?: number
    status?: string
    keyword?: string
  }): Promise<PageResp<KnowledgeEntry>> {
    try {
      const { data } = await http.get<PageResp<KnowledgeEntry>>('/knowledge/entries', { params })
      return data
    } catch (err) {
      throw new Error(errMsg(err, '获取知识库列表失败'))
    }
  },
  async createEntry(title: string, content: string): Promise<KnowledgeEntry> {
    try {
      const { data } = await http.post<KnowledgeEntry>('/knowledge/entries', { title, content })
      return data
    } catch (err) {
      throw new Error(errMsg(err, '创建条目失败'))
    }
  },
  async createFromUrl(url: string, title?: string): Promise<KnowledgeEntry> {
    try {
      const { data } = await http.post<KnowledgeEntry>('/knowledge/entries/url', {
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
      const { data } = await http.post<KnowledgeEntry>('/knowledge/entries/upload', form)
      return data
    } catch (err) {
      throw new Error(errMsg(err, '上传文件失败'))
    }
  },
  async getEntry(id: number): Promise<KnowledgeEntryDetail> {
    try {
      const { data } = await http.get<KnowledgeEntryDetail>(`/knowledge/entries/${id}`)
      return data
    } catch (err) {
      throw new Error(errMsg(err, '获取条目详情失败'))
    }
  },
  async reprocess(id: number): Promise<KnowledgeEntry> {
    try {
      const { data } = await http.post<KnowledgeEntry>(`/knowledge/entries/${id}/reprocess`)
      return data
    } catch (err) {
      throw new Error(errMsg(err, '重新处理失败'))
    }
  },
  async deleteEntry(id: number): Promise<void> {
    try {
      await http.delete(`/knowledge/entries/${id}`)
    } catch (err) {
      throw new Error(errMsg(err, '删除失败'))
    }
  },
  async search(query: string, topK = 5): Promise<SearchResp> {
    try {
      const { data } = await http.post<SearchResp>('/knowledge/search', { query, top_k: topK })
      return data
    } catch (err) {
      throw new Error(errMsg(err, '检索失败'))
    }
  },
  async overview(): Promise<KnowledgeOverview> {
    try {
      const { data } = await http.get<KnowledgeOverview>('/knowledge/stats/overview')
      return data
    } catch (err) {
      throw new Error(errMsg(err, '获取统计失败'))
    }
  },
}

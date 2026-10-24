import { QueryClient } from '@tanstack/react-query'

/**
 * 全局 QueryClient。
 * - staleTime 30s：单机工具数据变动不频繁，避免频繁重复请求
 * - retry 1：失败重试一次即止，避免离线/后端未启动时长时间卡住
 */
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
})

/**
 * 统一 queryKey 约定：`[域, ...参数]`。
 * 写操作后按域失效（invalidateQueries），保证列表/统计自动刷新。
 */
export const queryKeys = {
  knowledge: {
    all: ['knowledge'] as const,
    entries: (params: object) => ['knowledge', 'entries', params] as const,
    entry: (id: number) => ['knowledge', 'entry', id] as const,
    stats: ['knowledge', 'stats'] as const,
    search: (query: string) => ['knowledge', 'search', query] as const,
  },
  questions: {
    all: ['questions'] as const,
    list: (params: object) => ['questions', 'list', params] as const,
    detail: (id: number) => ['questions', 'detail', id] as const,
    stats: ['questions', 'stats'] as const,
  },
  exams: {
    all: ['exams'] as const,
    papers: (params: object) => ['exams', 'papers', params] as const,
    paper: (id: number) => ['exams', 'paper', id] as const,
    sessions: (params: object) => ['exams', 'sessions', params] as const,
    session: (id: number) => ['exams', 'session', id] as const,
  },
  wrong: {
    all: ['wrong'] as const,
    list: (params: object) => ['wrong', 'list', params] as const,
    stats: ['wrong', 'stats'] as const,
  },
  analytics: {
    questionOverview: ['analytics', 'question-overview'] as const,
    questionAccuracy: (limit: number) => ['analytics', 'question-accuracy', limit] as const,
    practiceOverview: ['analytics', 'practice-overview'] as const,
    practiceTrend: (days: number) => ['analytics', 'practice-trend', days] as const,
    practiceByType: ['analytics', 'practice-by-type'] as const,
    practiceRecent: (limit: number) => ['analytics', 'practice-recent', limit] as const,
  },
  settings: {
    config: ['settings', 'config'] as const,
  },
}

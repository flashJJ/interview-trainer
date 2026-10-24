import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { knowledgeApi } from '@/api/knowledge'
import { queryKeys } from '@/app/queryClient'

/** 知识库列表（分页 + 筛选）。 */
export function useKnowledgeEntries(params: {
  page?: number
  size?: number
  status?: string
  keyword?: string
}) {
  return useQuery({
    queryKey: queryKeys.knowledge.entries(params),
    queryFn: () => knowledgeApi.listEntries(params),
  })
}

/** 知识库总览统计（条目/块/向量数）。 */
export function useKnowledgeStats() {
  return useQuery({
    queryKey: queryKeys.knowledge.stats,
    queryFn: () => knowledgeApi.overview(),
  })
}

/** 条目详情（含 chunks），id 为空时禁用。 */
export function useKnowledgeEntry(id: number | null) {
  return useQuery({
    queryKey: queryKeys.knowledge.entry(id ?? 0),
    queryFn: () => knowledgeApi.getEntry(id as number),
    enabled: id != null,
  })
}

/** 语义检索（手动触发）。 */
export function useSemanticSearch() {
  return useMutation({
    mutationFn: ({ query, topK }: { query: string; topK?: number }) =>
      knowledgeApi.search(query, topK),
  })
}

/** 条目写操作：创建/上传/URL 导入/重处理/删除，成功后失效列表与统计。 */
export function useKnowledgeMutations() {
  const queryClient = useQueryClient()
  const invalidate = () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: queryKeys.knowledge.all }),
      queryClient.invalidateQueries({ queryKey: queryKeys.knowledge.stats }),
    ])

  const create = useMutation({
    mutationFn: ({ title, content }: { title: string; content: string }) =>
      knowledgeApi.createEntry(title, content),
    onSuccess: invalidate,
  })
  const upload = useMutation({
    mutationFn: ({ file, title }: { file: File; title?: string }) =>
      knowledgeApi.uploadEntry(file, title),
    onSuccess: invalidate,
  })
  const createFromUrl = useMutation({
    mutationFn: ({ url, title }: { url: string; title?: string }) =>
      knowledgeApi.createFromUrl(url, title),
    onSuccess: invalidate,
  })
  const reprocess = useMutation({
    mutationFn: (id: number) => knowledgeApi.reprocess(id),
    onSuccess: invalidate,
  })
  const remove = useMutation({
    mutationFn: (id: number) => knowledgeApi.deleteEntry(id),
    onSuccess: invalidate,
  })

  return { create, upload, createFromUrl, reprocess, remove }
}

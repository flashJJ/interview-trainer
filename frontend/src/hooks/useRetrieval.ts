import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { retrievalApi } from '@/api/retrieval'
import { queryKeys } from '@/app/queryClient'

/** 评测概览：用例数 / 知识块数 / 最近一次运行。 */
export function useEvalOverview() {
  return useQuery({
    queryKey: queryKeys.retrieval.overview,
    queryFn: () => retrievalApi.overview(),
  })
}

/** 评测集列表。 */
export function useEvalCases() {
  return useQuery({
    queryKey: queryKeys.retrieval.cases,
    queryFn: () => retrievalApi.listCases(),
  })
}

/** 评测历史（默认最近 10 次）。 */
export function useEvalRuns(limit = 10) {
  return useQuery({
    queryKey: queryKeys.retrieval.runs(limit),
    queryFn: () => retrievalApi.listRuns(limit),
  })
}

/** 单次运行明细（点开抽屉时才请求，故 enabled 控制）。 */
export function useEvalRun(id: number | null) {
  return useQuery({
    queryKey: queryKeys.retrieval.run(id ?? 0),
    queryFn: () => retrievalApi.getRun(id as number),
    enabled: id !== null,
  })
}

/** 评测相关写操作：生成 / 新增 / 删除 / 清空 / 运行。 */
export function useEvalMutations() {
  const queryClient = useQueryClient()
  const invalidateAll = () =>
    queryClient.invalidateQueries({ queryKey: queryKeys.retrieval.all })

  const autoBuild = useMutation({
    mutationFn: ({ count, useLlm }: { count: number; useLlm: boolean }) =>
      retrievalApi.autoBuild(count, useLlm),
    onSuccess: invalidateAll,
  })

  const createCase = useMutation({
    mutationFn: (payload: { query: string; expected_ids: number[]; note?: string }) =>
      retrievalApi.createCase(payload),
    onSuccess: invalidateAll,
  })

  const deleteCase = useMutation({
    mutationFn: (id: number) => retrievalApi.deleteCase(id),
    onSuccess: invalidateAll,
  })

  const clearCases = useMutation({
    mutationFn: () => retrievalApi.clearCases(),
    onSuccess: invalidateAll,
  })

  const run = useMutation({
    mutationFn: (payload: {
      top_k: number
      use_rewrite: boolean
      include_llm_rewrite?: boolean
      vector_weight: number
    }) => retrievalApi.run(payload),
    onSuccess: invalidateAll,
  })

  return { autoBuild, createCase, deleteCase, clearCases, run }
}

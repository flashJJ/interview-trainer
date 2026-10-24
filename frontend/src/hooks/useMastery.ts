import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { masteryApi } from '@/api/mastery'
import type { MasteryDim, QType } from '@/api/types'
import { queryKeys } from '@/app/queryClient'

/** 综合掌握度概览。 */
export function useMasteryOverview(threshold = 0.6) {
  return useQuery({
    queryKey: queryKeys.mastery.overview(threshold),
    queryFn: () => masteryApi.overview(threshold),
  })
}

/** 单维度掌握度（资料 / 题型 / 难度）。 */
export function useMasteryDimension(dim: MasteryDim) {
  return useQuery({
    queryKey: queryKeys.mastery.dimensions(dim),
    queryFn: () => masteryApi.dimensions(dim),
  })
}

/** 雷达数据（题型 3 轴 + 难度 3 轴）。 */
export function useMasteryRadar() {
  return useQuery({
    queryKey: queryKeys.mastery.radar,
    queryFn: () => masteryApi.radar(),
  })
}

/** 薄弱项列表。 */
export function useMasteryWeakPoints(threshold = 0.6, limit = 5) {
  return useQuery({
    queryKey: queryKeys.mastery.weak(threshold, limit),
    queryFn: () => masteryApi.weakPoints(threshold, limit),
  })
}

/** 定向组卷：成功后同时失效考试域缓存（考卷列表要能立刻看到新卷）。 */
export function useTargetedExam() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: {
      dim: MasteryDim
      key: string
      count: number
      types: QType[]
      title?: string
    }) => masteryApi.targetedExam(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.exams.all })
      queryClient.invalidateQueries({ queryKey: queryKeys.mastery.all })
    },
  })
}

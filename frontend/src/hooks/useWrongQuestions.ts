import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { wrongQuestionsApi } from '@/api/wrong-questions'
import { queryKeys } from '@/app/queryClient'
import type { QType } from '@/api/types'

/** 错题本列表（支持只看到期）。 */
export function useWrongQuestions(params: {
  page?: number
  size?: number
  q_type?: QType | ''
  only_due?: boolean
}) {
  return useQuery({
    queryKey: queryKeys.wrong.list(params),
    queryFn: () => wrongQuestionsApi.list(params),
  })
}

/** 错题统计（总数/今日待复习/逾期/未来 7 天）。 */
export function useWrongStats() {
  return useQuery({
    queryKey: queryKeys.wrong.stats,
    queryFn: () => wrongQuestionsApi.stats(),
  })
}

/** 错题本操作：生成复习卷/标记掌握/移出。 */
export function useWrongMutations() {
  const queryClient = useQueryClient()
  const invalidate = () => queryClient.invalidateQueries({ queryKey: queryKeys.wrong.all })

  const generateReview = useMutation({
    mutationFn: (count: number) => wrongQuestionsApi.generateReview(count),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.exams.all }),
  })
  const master = useMutation({
    mutationFn: (id: number) => wrongQuestionsApi.master(id),
    onSuccess: invalidate,
  })
  const remove = useMutation({
    mutationFn: (id: number) => wrongQuestionsApi.remove(id),
    onSuccess: invalidate,
  })

  return { generateReview, master, remove }
}

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { questionApi } from '@/api/questions'
import { queryKeys } from '@/app/queryClient'
import type { Difficulty, GenerateQuestionsReq, QuestionSource, QType } from '@/api/types'

/** 题库列表（按审核状态/题型/难度/来源/关键词筛选）。 */
export function useQuestions(params: {
  page?: number
  size?: number
  q_type?: QType | ''
  difficulty?: Difficulty | ''
  entry_id?: number
  keyword?: string
  source?: QuestionSource | ''
  review_status?: 'approved' | 'pending' | 'rejected' | 'all'
}) {
  return useQuery({
    queryKey: queryKeys.questions.list(params),
    queryFn: () => questionApi.list(params),
  })
}

/** 题库统计（含待审核数，菜单徽标用）。 */
export function useQuestionStats(refetchIntervalMs?: number) {
  return useQuery({
    queryKey: queryKeys.questions.stats,
    queryFn: () => questionApi.statsOverview(),
    refetchInterval: refetchIntervalMs,
  })
}

/** 题目写操作：出题/审核/批量审核/编辑/删除，成功后失效题库与题目统计。 */
export function useQuestionMutations() {
  const queryClient = useQueryClient()
  const invalidate = () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: queryKeys.questions.all }),
      queryClient.invalidateQueries({ queryKey: queryKeys.questions.stats }),
      queryClient.invalidateQueries({ queryKey: queryKeys.knowledge.all }),
      queryClient.invalidateQueries({ queryKey: queryKeys.analytics.questionOverview }),
    ])

  const generate = useMutation({
    mutationFn: (req: GenerateQuestionsReq) => questionApi.generate(req),
    onSuccess: invalidate,
  })
  const review = useMutation({
    mutationFn: ({ id, action }: { id: number; action: 'approve' | 'reject' }) =>
      questionApi.review(id, action),
    onSuccess: invalidate,
  })
  const batchReview = useMutation({
    mutationFn: ({ ids, action }: { ids: number[]; action: 'approve' | 'reject' }) =>
      questionApi.batchReview(ids, action),
    onSuccess: invalidate,
  })
  const update = useMutation({
    mutationFn: ({
      id,
      payload,
    }: {
      id: number
      payload: {
        content?: string
        options?: string[]
        answer?: string
        explanation?: string
        difficulty?: Difficulty
      }
    }) => questionApi.update(id, payload),
    onSuccess: invalidate,
  })
  const remove = useMutation({
    mutationFn: (id: number) => questionApi.remove(id),
    onSuccess: invalidate,
  })

  return { generate, review, batchReview, update, remove }
}

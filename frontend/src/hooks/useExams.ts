import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { examApi } from '@/api/exams'
import { queryKeys } from '@/app/queryClient'
import type { QType, SubmitExamReq } from '@/api/types'

/** 我的考卷列表。 */
export function useExamPapers(page = 1, size = 20) {
  return useQuery({
    queryKey: queryKeys.exams.papers({ page, size }),
    queryFn: () => examApi.list(page, size),
  })
}

/** 考卷详情（题目不含答案）。 */
export function useExamPaper(id: number | null) {
  return useQuery({
    queryKey: queryKeys.exams.paper(id ?? 0),
    queryFn: () => examApi.getPaper(id as number),
    enabled: id != null,
  })
}

/** 考试成绩详情。 */
export function useExamSession(id: number | null) {
  return useQuery({
    queryKey: queryKeys.exams.session(id ?? 0),
    queryFn: () => examApi.getSession(id as number),
    enabled: id != null,
  })
}

/** 历史考试列表。 */
export function useExamSessions(page = 1, size = 20) {
  return useQuery({
    queryKey: queryKeys.exams.sessions({ page, size }),
    queryFn: () => examApi.listSessions(page, size),
  })
}

/** 组卷与提交。 */
export function useExamMutations() {
  const queryClient = useQueryClient()

  const generate = useMutation({
    mutationFn: (params: {
      title?: string
      count: number
      types: QType[]
      difficulty?: string
      blueprint?: string
    }) => examApi.generate(params),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.exams.all }),
  })

  const submit = useMutation({
    mutationFn: ({
      sessionId,
      answers,
    }: {
      sessionId: number
      answers: SubmitExamReq['answers']
    }) => examApi.submit(sessionId, answers),
    onSuccess: () =>
      Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.exams.all }),
        queryClient.invalidateQueries({ queryKey: queryKeys.analytics.practiceOverview }),
        queryClient.invalidateQueries({ queryKey: queryKeys.wrong.all }),
      ]),
  })

  return { generate, submit }
}

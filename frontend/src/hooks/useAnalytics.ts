import { useQuery } from '@tanstack/react-query'
import { analyticsApi } from '@/api/analytics'
import { queryKeys } from '@/app/queryClient'

/** 题目分析：总览 + 正确率榜。 */
export function useQuestionAnalytics(accuracyLimit = 10) {
  const overview = useQuery({
    queryKey: queryKeys.analytics.questionOverview,
    queryFn: () => analyticsApi.questionsOverview(),
  })
  const accuracy = useQuery({
    queryKey: queryKeys.analytics.questionAccuracy(accuracyLimit),
    queryFn: () => analyticsApi.questionsAccuracy(accuracyLimit),
  })
  return { overview, accuracy }
}

/** 做题分析：总览 + 趋势 + 分题型 + 最近考试。 */
export function usePracticeAnalytics(days = 30, recentLimit = 10) {
  const overview = useQuery({
    queryKey: queryKeys.analytics.practiceOverview,
    queryFn: () => analyticsApi.practiceOverview(),
  })
  const trend = useQuery({
    queryKey: queryKeys.analytics.practiceTrend(days),
    queryFn: () => analyticsApi.practiceTrend(days),
  })
  const byType = useQuery({
    queryKey: queryKeys.analytics.practiceByType,
    queryFn: () => analyticsApi.practiceByType(),
  })
  const recent = useQuery({
    queryKey: queryKeys.analytics.practiceRecent(recentLimit),
    queryFn: () => analyticsApi.practiceRecent(recentLimit),
  })
  return { overview, trend, byType, recent }
}

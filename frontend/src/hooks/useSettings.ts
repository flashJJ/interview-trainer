import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { settingsApi } from '@/api/settings'
import { queryKeys } from '@/app/queryClient'
import type { SystemConfigIn } from '@/api/types'

/** 系统配置（LLM/Embedding 状态）。 */
export function useSettingsConfig() {
  return useQuery({
    queryKey: queryKeys.settings.config,
    queryFn: () => settingsApi.get(),
    staleTime: 10_000,
  })
}

/** 配置写操作：保存/恢复默认/测试连接/改密码。 */
export function useSettingsMutations() {
  const queryClient = useQueryClient()
  const invalidate = () => queryClient.invalidateQueries({ queryKey: queryKeys.settings.config })

  const save = useMutation({
    mutationFn: (payload: SystemConfigIn) => settingsApi.save(payload),
    onSuccess: invalidate,
  })
  const reset = useMutation({
    mutationFn: () => settingsApi.reset(),
    onSuccess: invalidate,
  })
  const test = useMutation({
    mutationFn: (payload: {
      target: 'llm' | 'embedding'
      llm_base_url?: string
      llm_api_key?: string
      llm_model?: string
      embedding_base_url?: string
      embedding_api_key?: string
      embedding_model?: string
    }) => settingsApi.test(payload),
  })
  const changePassword = useMutation({
    mutationFn: ({ oldPassword, newPassword }: { oldPassword: string; newPassword: string }) =>
      settingsApi.changePassword(oldPassword, newPassword),
  })

  return { save, reset, test, changePassword }
}

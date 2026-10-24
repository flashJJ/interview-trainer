import { errMsg, http } from './http'
import type { SystemConfig, SystemConfigIn, TestConnectionResult } from './types'

export const settingsApi = {
  async get(): Promise<SystemConfig> {
    try {
      const { data } = await http.get<SystemConfig>('/settings')
      return data
    } catch (err) {
      throw new Error(errMsg(err, '获取系统配置失败'))
    }
  },
  async save(payload: SystemConfigIn): Promise<SystemConfig> {
    try {
      const { data } = await http.put<SystemConfig>('/settings', payload)
      return data
    } catch (err) {
      throw new Error(errMsg(err, '保存配置失败'))
    }
  },
  async reset(): Promise<SystemConfig> {
    try {
      const { data } = await http.post<SystemConfig>('/settings/reset')
      return data
    } catch (err) {
      throw new Error(errMsg(err, '恢复默认失败'))
    }
  },
  async test(payload: {
    target: 'llm' | 'embedding'
    llm_base_url?: string
    llm_api_key?: string
    llm_model?: string
    embedding_base_url?: string
    embedding_api_key?: string
    embedding_model?: string
  }): Promise<TestConnectionResult> {
    try {
      const { data } = await http.post<TestConnectionResult>('/settings/test', payload)
      return data
    } catch (err) {
      throw new Error(errMsg(err, '测试连接失败'))
    }
  },
  async changePassword(
    oldPassword: string,
    newPassword: string,
  ): Promise<{ ok: boolean; message: string }> {
    try {
      const { data } = await http.post<{ ok: boolean; message: string }>('/settings/password', {
        old_password: oldPassword,
        new_password: newPassword,
      })
      return data
    } catch (err) {
      throw new Error(errMsg(err, '修改密码失败'))
    }
  },
}

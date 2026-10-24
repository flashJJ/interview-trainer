import { errMsg, http } from './http'
import type { LoginResp, User } from './types'

export const authApi = {
  async login(username: string, password: string): Promise<LoginResp> {
    try {
      const { data } = await http.post<LoginResp>('/auth/login', { username, password })
      return data
    } catch (err) {
      throw new Error(errMsg(err, '登录失败'))
    }
  },
  async register(username: string, password: string, email?: string): Promise<User> {
    try {
      const { data } = await http.post<User>('/auth/register', { username, password, email })
      return data
    } catch (err) {
      throw new Error(errMsg(err, '注册失败'))
    }
  },
  async me(): Promise<User> {
    try {
      const { data } = await http.get<User>('/auth/me')
      return data
    } catch (err) {
      throw new Error(errMsg(err, '获取用户信息失败'))
    }
  },
}

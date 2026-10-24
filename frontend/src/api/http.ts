import axios, { AxiosError } from 'axios'

export const TOKEN_KEY = 'it_token'

/** 全局 axios 实例：统一 baseURL、超时、鉴权与 401 处理。 */
export const http = axios.create({
  baseURL: '/api',
  timeout: 60000,
})

http.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY)
  if (token) {
    config.headers = config.headers ?? {}
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

http.interceptors.response.use(
  (resp) => resp,
  (error: AxiosError<{ detail?: string }>) => {
    if (error.response?.status === 401) {
      localStorage.removeItem(TOKEN_KEY)
      localStorage.removeItem('it_user')
      if (window.location.pathname !== '/login') {
        window.location.assign('/login')
      }
    }
    return Promise.reject(error)
  },
)

/** 从 axios 错误中提取后端 `detail` 文案，取不到时用兜底文案。 */
export function errMsg(err: unknown, fallback = '操作失败'): string {
  const e = err as AxiosError<{ detail?: string }>
  return e?.response?.data?.detail ?? fallback
}

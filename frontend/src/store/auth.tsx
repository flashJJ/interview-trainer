import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { authApi } from '../api/client'
import type { User } from '../api/types'

const TOKEN_KEY = 'it_token'
const USER_KEY = 'it_user'

interface AuthCtx {
  user: User | null
  token: string | null
  login: (username: string, password: string) => Promise<void>
  register: (username: string, password: string, email?: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthCtx | null>(null)

function readStoredUser(): User | null {
  try {
    const raw = localStorage.getItem(USER_KEY)
    return raw ? (JSON.parse(raw) as User) : null
  } catch {
    return null
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem(TOKEN_KEY))
  const [user, setUser] = useState<User | null>(readStoredUser)

  useEffect(() => {
    if (!token) return
    let cancelled = false
    authApi
      .me()
      .then((u) => {
        if (cancelled) return
        setUser(u)
        localStorage.setItem(USER_KEY, JSON.stringify(u))
      })
      .catch(() => {
        // 拦截器已处理 401 清理；其它错误保留本地用户信息
      })
    return () => {
      cancelled = true
    }
  }, [token])

  const login = useCallback(async (username: string, password: string) => {
    const resp = await authApi.login(username, password)
    localStorage.setItem(TOKEN_KEY, resp.access_token)
    localStorage.setItem(USER_KEY, JSON.stringify(resp.user))
    setToken(resp.access_token)
    setUser(resp.user)
  }, [])

  const register = useCallback(async (username: string, password: string, email?: string) => {
    await authApi.register(username, password, email)
  }, [])

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USER_KEY)
    setToken(null)
    setUser(null)
  }, [])

  const value = useMemo<AuthCtx>(
    () => ({ user, token, login, register, logout }),
    [user, token, login, register, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthCtx {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth 必须在 AuthProvider 内使用')
  return ctx
}

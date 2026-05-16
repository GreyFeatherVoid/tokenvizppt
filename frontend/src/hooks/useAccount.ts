import { useCallback, useEffect, useState } from 'react'
import { api, type AuthUser, type InviteStats } from '../lib/api'

export interface AccountState {
  user: AuthUser | null
  balance: number | null
  loading: boolean
  working: boolean
  loginOpen: boolean
  authError: string | null
  devCode: string | null
  codeSentTo: string | null
  codeCooldownSeconds: number
  canCheckin: boolean
  invite: InviteStats | null
  openLogin: () => void
  openRegister: () => void
  closeLogin: () => void
  refreshAccount: () => Promise<void>
  sendCode: (email: string, purpose?: 'login' | 'register') => Promise<void>
  login: (email: string, password: string, code?: string) => Promise<void>
  register: (email: string, password: string, code: string, referralCode?: string) => Promise<void>
  logout: () => Promise<void>
  checkin: () => Promise<void>
  authMode: 'login' | 'register'
  setAuthMode: (mode: 'login' | 'register') => void
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'Request failed'
}

export function useAccount(): AccountState {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [balance, setBalance] = useState<number | null>(null)
  const [loading, setLoading] = useState(true)
  const [working, setWorking] = useState(false)
  const [loginOpen, setLoginOpen] = useState(false)
  const [authError, setAuthError] = useState<string | null>(null)
  const [devCode, setDevCode] = useState<string | null>(null)
  const [codeSentTo, setCodeSentTo] = useState<string | null>(null)
  const [codeCooldownSeconds, setCodeCooldownSeconds] = useState(0)
  const [canCheckin, setCanCheckin] = useState(false)
  const [invite, setInvite] = useState<InviteStats | null>(null)
  const [authMode, setAuthMode] = useState<'login' | 'register'>('login')

  const refreshAccount = useCallback(async () => {
    setLoading(true)
    setAuthError(null)
    try {
      const result = await api.getMe()
      if (!result.authenticated || !result.user) {
        setUser(null)
        setBalance(null)
        setCanCheckin(false)
        setInvite(null)
        return
      }
      setUser(result.user)
      const credit = await api.getCreditBalance()
      setBalance(credit.points_balance)
      setCanCheckin(credit.can_checkin)
      const inviteStats = await api.getMyInvite()
      setInvite(inviteStats)
    } catch (error) {
      setUser(null)
      setBalance(null)
      setCanCheckin(false)
      setInvite(null)
      setAuthError(errorMessage(error))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void refreshAccount()
  }, [refreshAccount])

  useEffect(() => {
    if (codeCooldownSeconds <= 0) return
    const timer = window.setTimeout(() => {
      setCodeCooldownSeconds((current) => Math.max(0, current - 1))
    }, 1000)
    return () => window.clearTimeout(timer)
  }, [codeCooldownSeconds])

  const sendCode = useCallback(async (email: string, purpose: 'login' | 'register' = 'login') => {
    if (codeCooldownSeconds > 0) {
      return
    }
    setWorking(true)
    setAuthError(null)
    try {
      const result = await api.sendAuthCode(email, purpose)
      setCodeSentTo(email)
      setDevCode(result.dev_code ?? null)
      setCodeCooldownSeconds(result.resend_after_seconds)
    } catch (error) {
      setAuthError(errorMessage(error))
      throw error
    } finally {
      setWorking(false)
    }
  }, [codeCooldownSeconds])

  const login = useCallback(async (email: string, password: string, code?: string) => {
    setWorking(true)
    setAuthError(null)
    try {
      const result = await api.login(email, password, code)
      setUser(result.user)
      setBalance(result.user.points_balance)
      setLoginOpen(false)
      setDevCode(null)
      setCodeSentTo(null)
      const credit = await api.getCreditBalance()
      setBalance(credit.points_balance)
      setCanCheckin(credit.can_checkin)
      const inviteStats = await api.getMyInvite()
      setInvite(inviteStats)
    } catch (error) {
      setAuthError(errorMessage(error))
      throw error
    } finally {
      setWorking(false)
    }
  }, [])

  const register = useCallback(async (email: string, password: string, code: string, referralCode?: string) => {
    setWorking(true)
    setAuthError(null)
    try {
      const result = await api.register(email, password, code, referralCode)
      setUser(result.user)
      setBalance(result.user.points_balance)
      setLoginOpen(false)
      setDevCode(null)
      setCodeSentTo(null)
      const credit = await api.getCreditBalance()
      setBalance(credit.points_balance)
      setCanCheckin(credit.can_checkin)
      const inviteStats = await api.getMyInvite()
      setInvite(inviteStats)
    } catch (error) {
      setAuthError(errorMessage(error))
      throw error
    } finally {
      setWorking(false)
    }
  }, [])

  const logout = useCallback(async () => {
    setWorking(true)
    setAuthError(null)
    try {
      await api.logout()
      setUser(null)
      setBalance(null)
      setCanCheckin(false)
      setInvite(null)
    } catch (error) {
      setAuthError(errorMessage(error))
    } finally {
      setWorking(false)
    }
  }, [])

  const checkin = useCallback(async () => {
    setWorking(true)
    setAuthError(null)
    try {
      const result = await api.checkin()
      setBalance(result.points_balance)
      setCanCheckin(result.can_checkin)
      setUser((current) => (current ? { ...current, points_balance: result.points_balance } : current))
    } catch (error) {
      setAuthError(errorMessage(error))
    } finally {
      setWorking(false)
    }
  }, [])

  return {
    user,
    balance,
    loading,
    working,
    loginOpen,
    authError,
    devCode,
    codeSentTo,
    codeCooldownSeconds,
    canCheckin,
    invite,
    openLogin: () => {
      setAuthError(null)
      setAuthMode('login')
      setLoginOpen(true)
    },
    openRegister: () => {
      setAuthError(null)
      setAuthMode('register')
      setLoginOpen(true)
    },
    closeLogin: () => setLoginOpen(false),
    refreshAccount,
    sendCode,
    login,
    register,
    logout,
    checkin,
    authMode,
    setAuthMode,
  }
}

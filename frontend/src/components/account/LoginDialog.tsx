import { FormEvent, useEffect, useState } from 'react'
import { KeyRound, Loader2, Mail, UserPlus, X } from 'lucide-react'
import { useI18n } from '../../i18n'
import type { AccountState } from '../../hooks/useAccount'

interface LoginDialogProps {
  account: AccountState
}

export function LoginDialog({ account }: LoginDialogProps): React.JSX.Element | null {
  const { t } = useI18n()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [code, setCode] = useState('')
  const [referralCode, setReferralCode] = useState('')
  const [loginWithCode, setLoginWithCode] = useState(false)
  const isRegister = account.authMode === 'register'

  useEffect(() => {
    if (!account.loginOpen) {
      setPassword('')
      setConfirmPassword('')
      setCode('')
      setReferralCode('')
      setLoginWithCode(false)
    }
  }, [account.loginOpen])

  if (!account.loginOpen) {
    return null
  }

  async function handleSendCode(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault()
    if (!email.trim() || account.codeCooldownSeconds > 0) {
      return
    }
    await account.sendCode(email.trim(), isRegister ? 'register' : 'login')
  }

  async function handleLogin(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault()
    if (!email.trim() || (!password.trim() && !code.trim())) {
      return
    }
    await account.login(email.trim(), password, loginWithCode ? code.trim() : undefined)
  }

  async function handleRegister(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault()
    if (!email.trim() || !password || !code.trim()) {
      return
    }
    if (password !== confirmPassword) {
      return
    }
    await account.register(email.trim(), password, code.trim(), referralCode.trim() || undefined)
  }

  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={account.closeLogin}>
      <section
        className="login-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="login-title"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <header className="login-dialog-header">
          <div>
            <span className="eyebrow compact">
              {isRegister ? <UserPlus size={14} /> : <KeyRound size={14} />}
              {isRegister ? t('createAccount') : t('emailLogin')}
            </span>
            <h2 id="login-title">{isRegister ? t('createAccount') : t('signIn')}</h2>
          </div>
          <button className="icon-button" type="button" onClick={account.closeLogin} aria-label={t('close')}>
            <X size={18} />
          </button>
        </header>

        <div className="auth-tabs" role="tablist" aria-label="Account mode">
          <button
            className={isRegister ? 'secondary-button' : ''}
            type="button"
            onClick={() => account.setAuthMode('login')}
          >
            {t('signIn')}
          </button>
          <button
            className={isRegister ? '' : 'secondary-button'}
            type="button"
            onClick={() => account.setAuthMode('register')}
          >
            {t('register')}
          </button>
        </div>

        <form className="login-form" onSubmit={handleSendCode}>
          <label>
            {t('email')}
            <input
              type="email"
              value={email}
              autoComplete="email"
              placeholder="name@example.com"
              onChange={(event) => setEmail(event.target.value)}
            />
          </label>
          <button
            type="submit"
            disabled={account.working || !email.trim() || account.codeCooldownSeconds > 0}
          >
            {account.working ? <Loader2 className="spin" size={18} /> : <Mail size={18} />}
            {account.codeCooldownSeconds > 0
              ? `${t('resendAfter')} ${account.codeCooldownSeconds}s`
              : isRegister || loginWithCode
                ? t('sendCode')
                : t('sendLoginCode')}
          </button>
        </form>

        {!isRegister ? (
          <form className="login-form" onSubmit={handleLogin}>
            <label>
              {t('password')}
              <input
                type="password"
                value={password}
                autoComplete="current-password"
                onChange={(event) => setPassword(event.target.value)}
              />
            </label>
            <label className="inline-check">
              <input
                type="checkbox"
                checked={loginWithCode}
                onChange={(event) => setLoginWithCode(event.target.checked)}
              />
              {t('loginWithCode')}
            </label>
            {loginWithCode ? (
              <label>
                {t('verificationCode')}
                <input
                  inputMode="numeric"
                  value={code}
                  autoComplete="one-time-code"
                  onChange={(event) => setCode(event.target.value)}
                />
              </label>
            ) : null}
            {account.devCode ? (
              <p className="dev-code">
                {t('devCode')}: <strong>{account.devCode}</strong>
              </p>
            ) : null}
            <button type="submit" disabled={account.working || (!password.trim() && !code.trim())}>
              {account.working ? <Loader2 className="spin" size={18} /> : null}
              {t('login')}
            </button>
          </form>
        ) : null}

        {isRegister ? (
          <form className="login-form" onSubmit={handleRegister}>
            <label>
              {t('password')}
              <input
                type="password"
                value={password}
                autoComplete="new-password"
                minLength={8}
                onChange={(event) => setPassword(event.target.value)}
              />
            </label>
            <label>
              {t('confirmPassword')}
              <input
                type="password"
                value={confirmPassword}
                autoComplete="new-password"
                minLength={8}
                onChange={(event) => setConfirmPassword(event.target.value)}
              />
            </label>
            <label>
              {t('verificationCode')}
              <input
                inputMode="numeric"
                value={code}
                autoComplete="one-time-code"
                onChange={(event) => setCode(event.target.value)}
              />
            </label>
            <label>
              {t('referralCode')}
              <input
                value={referralCode}
                autoComplete="off"
                onChange={(event) => setReferralCode(event.target.value)}
              />
            </label>
            {account.devCode ? (
              <p className="dev-code">
                {t('devCode')}: <strong>{account.devCode}</strong>
              </p>
            ) : null}
            {password && confirmPassword && password !== confirmPassword ? (
              <p className="error-text">{t('passwordMismatch')}</p>
            ) : null}
            {password && password.length < 8 ? <p className="error-text">{t('passwordTooShort')}</p> : null}
            <button
              type="submit"
              disabled={
                account.working ||
                password.length < 8 ||
                password !== confirmPassword ||
                !code.trim()
              }
            >
              {account.working ? <Loader2 className="spin" size={18} /> : <UserPlus size={18} />}
              {t('register')}
            </button>
          </form>
        ) : null}

        {account.authError ? <p className="error-text">{account.authError}</p> : null}
      </section>
    </div>
  )
}

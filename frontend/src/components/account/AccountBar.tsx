import { Check, Coins, LogIn, LogOut, Loader2, Shield, UserPlus } from 'lucide-react'
import { useI18n } from '../../i18n'
import type { AccountState } from '../../hooks/useAccount'

interface AccountBarProps {
  account: AccountState
  adminAvailable?: boolean
  onOpenAdmin?: () => void
}

export function AccountBar({ account, adminAvailable = false, onOpenAdmin }: AccountBarProps): React.JSX.Element {
  const { t } = useI18n()

  if (account.loading) {
    return (
      <div className="account-bar">
        <Loader2 className="spin" size={16} />
        <span>{t('loading')}</span>
      </div>
    )
  }

  if (!account.user) {
    return (
      <div className="account-actions">
        <button className="account-signin" type="button" onClick={account.openRegister}>
          <UserPlus size={18} />
          {t('register')}
        </button>
        <button className="account-signin secondary-button" type="button" onClick={account.openLogin}>
          <LogIn size={18} />
          {t('signIn')}
        </button>
      </div>
    )
  }

  return (
    <div className="account-bar">
      <span className="account-email">{account.user.email}</span>
      <span className="account-points">
        <Coins size={16} />
        {account.balance ?? account.user.points_balance} {t('points')}
      </span>
      {account.invite ? (
        <span className="account-invite" title={`${account.invite.rewarded_invites}/${account.invite.total_invites} ${t('inviteStats')}`}>
          {t('inviteCodeLabel')}: {account.invite.invite_code}
        </span>
      ) : null}
      <button
        className="secondary-button compact-button"
        type="button"
        onClick={account.checkin}
        disabled={account.working || !account.canCheckin}
      >
        {account.working ? <Loader2 className="spin" size={16} /> : <Check size={16} />}
        {account.canCheckin ? t('checkIn') : t('checkedIn')}
      </button>
      {adminAvailable && onOpenAdmin ? (
        <button className="secondary-button compact-button" type="button" onClick={onOpenAdmin}>
          <Shield size={16} />
          {t('admin')}
        </button>
      ) : null}
      <button className="icon-button subtle-button" type="button" onClick={account.logout} disabled={account.working} aria-label={t('signOut')}>
        <LogOut size={17} />
      </button>
    </div>
  )
}

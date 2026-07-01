import {
  ArrowRight,
  BarChart3,
  BookOpen,
  ChartPie,
  Coins,
  FileText,
  Gift,
  LineChart,
  Link,
  Mail,
  Plus,
  Sparkles,
  Upload,
  UserCircle,
} from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { AccountBar } from '../components/account/AccountBar'
import { LoginDialog } from '../components/account/LoginDialog'
import { AdminPanel } from '../components/admin/AdminPanel'
import { DeckWorkspace } from '../components/deck/DeckWorkspace'
import { GenerationForm } from '../components/generation/GenerationForm'
import { ProgressPanel } from '../components/generation/ProgressPanel'
import { RecentDecks } from '../components/generation/RecentDecks'
import { useAccount } from '../hooks/useAccount'
import { useDeckGeneration } from '../hooks/useDeckGeneration'
import { I18nContext, messages, useI18n, type UiLanguage } from '../i18n'
import { api } from '../lib/api'
import type { Announcement, CreditHistoryEntry, SessionSummary } from '../lib/api'

type ThemeId = 'mint' | 'sky' | 'lime' | 'sea-salt'

const THEME_STORAGE_KEY = 'tokenvizppt:theme'

const themeOptions: Array<{
  id: ThemeId
  en: string
  zh: string
}> = [
  { id: 'mint', en: 'Mint', zh: '清新微风' },
  { id: 'sky', en: 'Sky Blue', zh: '天空雾蓝' },
  { id: 'lime', en: 'Lime', zh: '薄荷清晨' },
  { id: 'sea-salt', en: 'Sea Salt', zh: '海盐青灰' },
]

function readStoredTheme(): ThemeId {
  const stored = window.localStorage.getItem(THEME_STORAGE_KEY)
  return themeOptions.some((option) => option.id === stored) ? (stored as ThemeId) : 'mint'
}

export function HomePage(): React.JSX.Element {
  const account = useAccount()
  const deckSectionRef = useRef<HTMLDivElement | null>(null)
  const [workspaceOpen, setWorkspaceOpen] = useState(false)
  const [activeView, setActiveView] = useState<'home' | 'workspace' | 'account'>('home')
  const isWorkspace = activeView === 'workspace' || workspaceOpen
  const generation = useDeckGeneration({ enabled: isWorkspace })
  const [adminAvailable, setAdminAvailable] = useState(false)
  const [adminOpen, setAdminOpen] = useState(false)
  const [announcements, setAnnouncements] = useState<Announcement[]>([])
  const [language, setLanguage] = useState<UiLanguage>(() =>
    navigator.language.toLowerCase().startsWith('zh') ? 'zh-CN' : 'en-US',
  )
  const [theme, setTheme] = useState<ThemeId>(readStoredTheme)
  const i18n = useMemo(
    () => ({
      language,
      t: (key: keyof typeof messages['en-US']) => messages[language][key],
    }),
    [language],
  )

  useEffect(() => {
    if (!generation.completionNotice) return
    const originalTitle = document.title
    document.title = i18n.t('notifyReadyTitle')
    if (generation.notificationsEnabled && typeof Notification !== 'undefined') {
      new Notification(i18n.t('notifyReadyTitle'), {
        body: i18n.t('notifyReadyBody'),
      })
    }
    const timeout = window.setTimeout(() => {
      document.title = originalTitle
    }, 9000)
    return () => {
      window.clearTimeout(timeout)
      document.title = originalTitle
    }
  }, [generation.completionNotice, generation.notificationsEnabled, i18n])

  useEffect(() => {
    if (!account.user) {
      setAdminAvailable(false)
      setAdminOpen(false)
      return
    }
    void api
      .getAdminMe()
      .then(() => setAdminAvailable(true))
      .catch(() => setAdminAvailable(false))
  }, [account.user?.id])

  useEffect(() => {
    window.localStorage.setItem(THEME_STORAGE_KEY, theme)
  }, [theme])

  useEffect(() => {
    void api
      .getAnnouncements(3)
      .then((result) => setAnnouncements(result.announcements))
      .catch(() => setAnnouncements([]))
  }, [])

  return (
    <I18nContext.Provider value={i18n}>
      <main className="app-shell" data-theme={theme}>
      <nav className="site-nav" aria-label="Primary">
        <button
          className="brand-button"
          type="button"
          onClick={() => {
            setActiveView('home')
            setWorkspaceOpen(false)
            setAdminOpen(false)
          }}
        >
          <span>tokenviz</span>
          <span className="brand-accent">PPT</span>
        </button>
        <div className="nav-links">
          <button
            className={activeView === 'home' ? 'active' : ''}
            type="button"
            onClick={() => {
              setActiveView('home')
              setWorkspaceOpen(false)
              setAdminOpen(false)
            }}
          >
            {i18n.t('home')}
          </button>
          <button
            className={activeView === 'workspace' ? 'active' : ''}
            type="button"
            onClick={() => {
              setActiveView('workspace')
              setWorkspaceOpen(true)
              setAdminOpen(false)
            }}
          >
            {i18n.t('workspaceNav')}
          </button>
          <button
            className={activeView === 'account' ? 'active' : ''}
            type="button"
            onClick={() => {
              setActiveView('account')
              setWorkspaceOpen(false)
              setAdminOpen(false)
            }}
          >
            {i18n.t('myAccount')}
          </button>
        </div>
        <div className="nav-actions">
          <label className="theme-switcher">
            <span>{i18n.t('theme')}</span>
            <select value={theme} onChange={(event) => setTheme(event.target.value as ThemeId)}>
              {themeOptions.map((option) => (
                <option key={option.id} value={option.id}>
                  {language === 'zh-CN' ? option.zh : option.en}
                </option>
              ))}
            </select>
          </label>
          <button
            className="language-toggle"
            type="button"
            onClick={() => setLanguage((current) => (current === 'zh-CN' ? 'en-US' : 'zh-CN'))}
          >
            {i18n.t('languageToggle')}
          </button>
          <AccountBar
            account={account}
            adminAvailable={adminAvailable}
            onOpenAdmin={() => {
              setAdminOpen(true)
              setActiveView('account')
            }}
          />
        </div>
      </nav>

      {activeView !== 'account' ? (
        !isWorkspace ? (
          <LandingHero
            onUse={() => {
              setActiveView('workspace')
              setWorkspaceOpen(true)
            }}
            onRegister={account.openRegister}
            announcements={announcements}
          />
        ) : (
          <section className="hero-panel compact-hero">
            <div className="eyebrow">
              <Sparkles size={16} />
              {i18n.t('aiWorkbench')}
            </div>
            <h1>
              <span>tokenviz</span>
              <span className="brand-accent">PPT</span>
            </h1>
            <p>{i18n.t('heroDescription')}</p>
          </section>
        )
      ) : null}

      {adminOpen ? (
        <AdminPanel onClose={() => setAdminOpen(false)} />
      ) : activeView === 'account' ? (
        <AccountPage account={account} />
      ) : !isWorkspace ? (
        <LandingContent
          onUse={() => {
            setActiveView('workspace')
            setWorkspaceOpen(true)
          }}
          announcements={announcements}
        />
      ) : (
        <>
          {account.user ? (
            <RecentDecks
              sessions={generation.sessions}
              loading={generation.sessionsLoading}
              activeSessionId={generation.sessionId}
              onOpen={generation.openSession}
              onDelete={generation.deleteSavedSession}
            />
          ) : null}

          <section className="workspace">
            <GenerationForm
              loading={generation.loading}
              error={generation.error}
              onSubmit={async (payload) => {
                await generation.startGeneration(payload)
                if (account.user) {
                  await account.refreshAccount()
                }
              }}
            />
            <ProgressPanel
              events={generation.events}
              latestProgress={generation.latestProgress}
              sessionId={generation.sessionId}
              loading={generation.loading}
              completed={Boolean(generation.deck) && !generation.loading}
              onViewDeck={() => deckSectionRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })}
              notificationAvailable={
                generation.notificationsSupported && !generation.notificationsEnabled
              }
              onEnableNotifications={generation.enableCompletionNotifications}
            />
          </section>

          {generation.deck ? (
            <div ref={deckSectionRef}>
              <DeckWorkspace
                deck={generation.deck}
                selectedSlide={generation.selectedSlide}
                selectedSlideId={generation.selectedSlideId}
                editing={generation.editing}
                editError={generation.editError}
                slideVersions={generation.slideVersions}
                historyLoading={generation.historyLoading}
                assets={generation.assets}
                assetLoading={generation.assetLoading}
                exporting={generation.exporting}
                exportUrl={generation.exportUrl}
                onSelectSlide={generation.setSelectedSlideId}
                onEditSlide={generation.editSelectedSlide}
                onPatchElement={generation.patchSelectedElement}
                onUploadAsset={generation.uploadAsset}
                onInsertAsset={generation.insertAssetIntoSelectedSlide}
                onPlaceAsset={generation.placeAssetInSelectedSlide}
                onExportPptx={generation.exportEditablePptx}
                onRollbackSlide={generation.rollbackSelectedSlide}
              />
            </div>
          ) : null}
        </>
      )}
      {generation.completionNotice ? (
        <div className="completion-toast" role="status">
          <strong>{i18n.t('notifyReadyTitle')}</strong>
          <span>{i18n.t('notifyReadyBody')}</span>
          <button type="button" onClick={generation.dismissCompletionNotice}>
            {i18n.t('close')}
          </button>
        </div>
      ) : null}
      <LoginDialog account={account} />
      </main>
    </I18nContext.Provider>
  )
}

function LandingHero({
  onUse,
  onRegister,
  announcements,
}: {
  onUse: () => void
  onRegister: () => void
  announcements: Announcement[]
}): React.JSX.Element {
  const { t } = useI18n()

  return (
    <section className="landing-hero-shell">
      <div className="landing-hero-copy">
        <span className="eyebrow compact hero-badge">
          <Sparkles size={15} />
          {t('aiWorkbench')}
        </span>
        <h1>
          <span>tokenviz</span>
          <span className="brand-accent">PPT</span>
        </h1>
        <p>{t('heroDescription')}</p>
        <div className="landing-actions">
          <button className="hero-primary-action" type="button" onClick={onUse}>
            {t('useNow')}
            <ArrowRight size={19} />
          </button>
          <button className="secondary-button hero-secondary-action" type="button" onClick={onRegister}>
            <Gift size={18} />
            {t('freeTrial')}
          </button>
        </div>
        <div className="hero-proof-row">
          <span>
            <Sparkles size={15} />
            {t('signupCredits')}
          </span>
          <span>
            <Coins size={15} />
            {t('dailyFreeGeneration')}
          </span>
          <span>
            <FileText size={15} />
            {t('editablePptx')}
          </span>
        </div>
        {announcements.length ? (
          <div className="announcement-strip">
            <strong>{t('announcements')}</strong>
            <span>{announcements[0].title}</span>
          </div>
        ) : null}
      </div>

      <div className="product-visual" aria-hidden="true">
        <div className="visual-panel main"></div>
        <div className="visual-panel side"></div>
        <div className="mock-window">
          <aside className="mock-sidebar">
            <strong>tokenvizPPT</strong>
            <button type="button">
              <Plus size={14} />
              {t('newDeck')}
            </button>
            <span>{t('aiGenerate')}</span>
            <span>{t('myFiles')}</span>
            <span>{t('templateCenter')}</span>
          </aside>
          <div className="mock-workspace">
            <span className="mock-kicker">AI</span>
            <h2>{t('heroMockTitle')}</h2>
            <p>{t('heroMockDescription')}</p>
            <div className="mock-prompt">
              <span>{t('heroMockPlaceholder')}</span>
              <div>
                <button type="button">
                  <Upload size={13} />
                  {t('uploadFile')}
                </button>
                <button type="button">
                  <FileText size={13} />
                  {t('pasteText')}
                </button>
                <button type="button">
                  <Link size={13} />
                  {t('importLink')}
                </button>
              </div>
              <button className="mock-submit" type="button">
                {t('generatePpt')}
                <ArrowRight size={15} />
              </button>
            </div>
            <div className="mock-template-row">
              <article>
                <span className="template-cover blue"></span>
                <strong>{t('caseProductLaunch')}</strong>
              </article>
              <article>
                <span className="template-cover navy"></span>
                <strong>{t('caseWeeklyReport')}</strong>
              </article>
              <article>
                <span className="template-cover green"></span>
                <strong>{t('caseCourseDeck')}</strong>
              </article>
            </div>
          </div>
        </div>
        <div className="floating-file chart">
          <ChartPie size={34} />
        </div>
        <div className="floating-file ppt">
          <strong>P</strong>
        </div>
      </div>
    </section>
  )
}

function LandingContent({
  onUse,
  announcements,
}: {
  onUse: () => void
  announcements: Announcement[]
}): React.JSX.Element {
  const { t } = useI18n()
  const examples = [
    {
      icon: LineChart,
      title: t('caseProductLaunch'),
      detail: t('caseProductLaunchDetail'),
    },
    {
      icon: BarChart3,
      title: t('caseWeeklyReport'),
      detail: t('caseWeeklyReportDetail'),
    },
    {
      icon: BookOpen,
      title: t('caseCourseDeck'),
      detail: t('caseCourseDeckDetail'),
    },
  ]

  return (
    <section className="landing-content">
      <div className="landing-rule">
        <span className="eyebrow compact">
          <Sparkles size={14} />
          {t('freeTrial')}
        </span>
        <h2>{t('freeTrialTitle')}</h2>
        <p>{t('freeTrialDescription')}</p>
        <button type="button" onClick={onUse}>
          {t('useNow')}
          <ArrowRight size={18} />
        </button>
      </div>
      <div className="case-grid">
        {examples.map((example, index) => {
          const Icon = example.icon
          return (
          <article className={`case-card case-card-${index + 1}`} key={example.title}>
            <span className="case-icon">
              <Icon size={26} />
            </span>
            <h3>{example.title}</h3>
            <p>{example.detail}</p>
            <button className="case-link" type="button" onClick={onUse}>
              {t('useNow')}
              <ArrowRight size={16} />
            </button>
          </article>
          )
        })}
      </div>
      <section className="announcement-board">
        <div>
          <span className="eyebrow compact">
            <Mail size={14} />
            {t('announcements')}
          </span>
        </div>
        {announcements.length ? (
          announcements.map((announcement) => (
            <article key={announcement.id}>
              <strong>{announcement.title}</strong>
              <p>{announcement.body}</p>
            </article>
          ))
        ) : (
          <p className="muted-text">{t('announcementsEmpty')}</p>
        )}
      </section>
    </section>
  )
}

function AccountPage({ account }: { account: ReturnType<typeof useAccount> }): React.JSX.Element {
  const { t } = useI18n()
  const [sessions, setSessions] = useState<SessionSummary[]>([])
  const [credits, setCredits] = useState<CreditHistoryEntry[]>([])
  const [detailLoading, setDetailLoading] = useState(false)

  useEffect(() => {
    if (!account.user) {
      setSessions([])
      setCredits([])
      return
    }
    setDetailLoading(true)
    void Promise.all([api.listSessions(), api.getCreditHistory(20)])
      .then(([sessionResult, creditResult]) => {
        setSessions(sessionResult.sessions)
        setCredits(creditResult.entries)
      })
      .catch(() => {
        setSessions([])
        setCredits([])
      })
      .finally(() => setDetailLoading(false))
  }, [account.user?.id])

  if (!account.user) {
    return (
      <section className="account-page empty-account">
        <UserCircle size={34} />
        <h2>{t('myAccount')}</h2>
        <p>{t('accountLoginHint')}</p>
        <div className="landing-actions">
          <button type="button" onClick={account.openRegister}>
            {t('register')}
          </button>
          <button className="secondary-button" type="button" onClick={account.openLogin}>
            {t('signIn')}
          </button>
        </div>
      </section>
    )
  }

  return (
    <section className="account-page">
      <header className="account-page-header">
        <div>
          <span className="eyebrow compact">
            <UserCircle size={14} />
            {t('myAccount')}
          </span>
          <h2>{account.user.email}</h2>
        </div>
        <button className="secondary-button" type="button" onClick={account.logout} disabled={account.working}>
          {t('signOut')}
        </button>
      </header>

      <div className="account-metrics">
        <article>
          <Coins size={22} />
          <span>{t('points')}</span>
          <strong>{account.balance ?? account.user.points_balance}</strong>
        </article>
        <article>
          <Gift size={22} />
          <span>{t('inviteCodeLabel')}</span>
          <strong>{account.invite?.invite_code ?? account.user.invite_code ?? '-'}</strong>
        </article>
        <article>
          <Mail size={22} />
          <span>{t('accountStatus')}</span>
          <strong>{account.user.status}</strong>
        </article>
      </div>

      <div className="account-detail-grid">
        <section>
          <h3>{t('creditActions')}</h3>
          <p>{t('creditActionsDescription')}</p>
          <button type="button" onClick={account.checkin} disabled={account.working || !account.canCheckin}>
            {account.canCheckin ? t('checkIn') : t('checkedIn')}
          </button>
        </section>
        <section>
          <h3>{t('inviteStats')}</h3>
          <p>
            {t('totalInvites')}: {account.invite?.total_invites ?? 0}
          </p>
          <p>
            {t('rewardedInvites')}: {account.invite?.rewarded_invites ?? 0}
          </p>
          <p>
            {t('pendingInvites')}: {account.invite?.pending_invites ?? 0}
          </p>
        </section>
      </div>

      <div className="account-history-grid">
        <section>
          <h3>{t('accountProjects')}</h3>
          {detailLoading ? <p className="muted-text">{t('loading')}</p> : null}
          <ul>
            {sessions.slice(0, 8).map((session) => (
              <li key={session.id}>
                <strong>{session.topic}</strong>
                <span>{session.status} · {session.slide_count} {t('slidesUnit')}</span>
              </li>
            ))}
          </ul>
          {!detailLoading && !sessions.length ? <p className="muted-text">{t('noAccountProjects')}</p> : null}
        </section>
        <section>
          <h3>{t('accountCreditLedger')}</h3>
          {detailLoading ? <p className="muted-text">{t('loading')}</p> : null}
          <ul>
            {credits.slice(0, 10).map((entry) => (
              <li key={entry.id}>
                <strong>{entry.amount > 0 ? '+' : ''}{entry.amount}</strong>
                <span>{entry.reason} · {entry.balance_after}</span>
              </li>
            ))}
          </ul>
          {!detailLoading && !credits.length ? <p className="muted-text">{t('noCreditHistory')}</p> : null}
        </section>
      </div>
    </section>
  )
}

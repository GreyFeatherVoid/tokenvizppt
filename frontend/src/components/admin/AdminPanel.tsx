import { FormEvent, useEffect, useMemo, useState } from 'react'
import {
  Ban,
  CheckCircle2,
  Coins,
  Megaphone,
  KeyRound,
  Loader2,
  RefreshCw,
  Search,
  Shield,
  Square,
  UserCog,
} from 'lucide-react'
import {
  api,
  type AdminAuditLog,
  type AdminDashboardStats,
  type AdminGenerationRun,
  type AdminSessionSummary,
  type AdminUser,
  type Announcement,
  type CreditHistoryEntry,
  type CreditRule,
  type ProviderConfig,
} from '../../lib/api'

interface AdminPanelProps {
  onClose: () => void
}

export function AdminPanel({ onClose }: AdminPanelProps): React.JSX.Element {
  const [users, setUsers] = useState<AdminUser[]>([])
  const [selectedUserId, setSelectedUserId] = useState<string | null>(null)
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(true)
  const [working, setWorking] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [credits, setCredits] = useState<CreditHistoryEntry[]>([])
  const [sessions, setSessions] = useState<AdminSessionSummary[]>([])
  const [runs, setRuns] = useState<AdminGenerationRun[]>([])
  const [dashboard, setDashboard] = useState<AdminDashboardStats | null>(null)
  const [announcements, setAnnouncements] = useState<Announcement[]>([])
  const [creditRules, setCreditRules] = useState<CreditRule[]>([])
  const [providerConfigs, setProviderConfigs] = useState<ProviderConfig[]>([])
  const [runStatus, setRunStatus] = useState('queued')
  const [runMessage, setRunMessage] = useState<string | null>(null)
  const [auditLogs, setAuditLogs] = useState<AdminAuditLog[]>([])
  const [creditAmount, setCreditAmount] = useState(30)
  const [creditReason, setCreditReason] = useState('Manual adjustment')
  const [editingAnnouncementId, setEditingAnnouncementId] = useState<string | undefined>()
  const [announcementTitle, setAnnouncementTitle] = useState('')
  const [announcementBody, setAnnouncementBody] = useState('')
  const [announcementStatus, setAnnouncementStatus] = useState('draft')
  const [editingProviderConfigId, setEditingProviderConfigId] = useState<string | undefined>()
  const [providerType, setProviderType] = useState<'llm' | 'ai_image'>('llm')
  const [providerName, setProviderName] = useState('OpenAI compatible')
  const [providerModel, setProviderModel] = useState('')
  const [providerBaseUrl, setProviderBaseUrl] = useState('')
  const [providerApiKey, setProviderApiKey] = useState('')
  const [providerStatus, setProviderStatus] = useState('disabled')

  const selectedUser = useMemo(
    () => users.find((user) => user.id === selectedUserId) ?? users[0] ?? null,
    [selectedUserId, users],
  )

  async function loadUsers(nextQuery = query): Promise<void> {
    setLoading(true)
    setError(null)
    try {
      const result = await api.listAdminUsers({ q: nextQuery.trim() || undefined })
      setUsers(result.users)
      setSelectedUserId((current) => {
        if (current && result.users.some((user) => user.id === current)) return current
        return result.users[0]?.id ?? null
      })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load users')
    } finally {
      setLoading(false)
    }
  }

  async function loadUserDetails(userId: string): Promise<void> {
    setError(null)
    try {
      const [creditResult, sessionResult] = await Promise.all([
        api.getAdminUserCredits(userId),
        api.getAdminUserSessions(userId),
      ])
      setCredits(creditResult.entries)
      setSessions(sessionResult.sessions)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load user details')
      setCredits([])
      setSessions([])
    }
  }

  async function loadAuditLogs(): Promise<void> {
    try {
      const result = await api.getAdminAuditLogs()
      setAuditLogs(result.logs)
    } catch {
      setAuditLogs([])
    }
  }

  async function loadRuns(status = runStatus): Promise<void> {
    try {
      const result = await api.getAdminGenerationRuns({
        status: status === 'all' ? undefined : status,
        limit: 30,
      })
      setRuns(result.runs)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load generation runs')
      setRuns([])
    }
  }

  async function loadAdminSettings(): Promise<void> {
    try {
      const [dashboardResult, announcementsResult, ruleResult, providerResult] = await Promise.all([
        api.getAdminDashboard(),
        api.getAdminAnnouncements('all'),
        api.getAdminCreditRules(),
        api.getAdminProviderConfigs(),
      ])
      setDashboard(dashboardResult)
      setAnnouncements(announcementsResult.announcements)
      setCreditRules(ruleResult.rules)
      setProviderConfigs(providerResult.configs)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load admin settings')
    }
  }

  useEffect(() => {
    void loadUsers()
    void loadAuditLogs()
    void loadRuns()
    void loadAdminSettings()
  }, [])

  useEffect(() => {
    void loadRuns(runStatus)
  }, [runStatus])

  useEffect(() => {
    if (selectedUser?.id) {
      void loadUserDetails(selectedUser.id)
    } else {
      setCredits([])
      setSessions([])
    }
  }, [selectedUser?.id])

  async function handleSearch(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault()
    await loadUsers(query)
  }

  async function updateUser(payload: { status?: string; role?: string }): Promise<void> {
    if (!selectedUser) return
    setWorking(true)
    setError(null)
    try {
      const updated = await api.updateAdminUser(selectedUser.id, payload)
      setUsers((current) => current.map((user) => (user.id === updated.id ? updated : user)))
      await loadAuditLogs()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update user')
    } finally {
      setWorking(false)
    }
  }

  async function adjustCredits(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault()
    if (!selectedUser) return
    setWorking(true)
    setError(null)
    try {
      const result = await api.adjustAdminUserCredits(selectedUser.id, {
        amount: Number(creditAmount),
        reason: creditReason,
      })
      setUsers((current) => current.map((user) => (user.id === result.user.id ? result.user : user)))
      await Promise.all([loadUserDetails(selectedUser.id), loadAuditLogs()])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to adjust credits')
    } finally {
      setWorking(false)
    }
  }

  async function cancelRun(run: AdminGenerationRun): Promise<void> {
    const reason = window.prompt('Cancel reason', 'Cancelled by admin')
    if (!reason) return
    setWorking(true)
    setRunMessage(null)
    setError(null)
    try {
      const result = await api.cancelAdminGenerationRun(run.id, reason)
      setRunMessage(
        result.refunded_credits > 0
          ? `Cancelled ${run.id}. Refunded ${result.refunded_credits} credits.`
          : `Cancelled ${run.id}. No credits were charged.`,
      )
      await Promise.all([
        loadRuns(runStatus),
        loadAuditLogs(),
        selectedUser ? loadUserDetails(selectedUser.id) : Promise.resolve(),
      ])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to cancel generation run')
    } finally {
      setWorking(false)
    }
  }

  async function saveAnnouncement(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault()
    setWorking(true)
    setError(null)
    try {
      await api.saveAdminAnnouncement({
        id: editingAnnouncementId,
        title: announcementTitle,
        body: announcementBody,
        status: announcementStatus,
      })
      setEditingAnnouncementId(undefined)
      setAnnouncementTitle('')
      setAnnouncementBody('')
      setAnnouncementStatus('draft')
      await Promise.all([loadAdminSettings(), loadAuditLogs()])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save announcement')
    } finally {
      setWorking(false)
    }
  }

  async function updateRule(rule: CreditRule, amount: number, enabled: boolean): Promise<void> {
    setWorking(true)
    setError(null)
    try {
      const updated = await api.updateAdminCreditRule(rule.action, { amount, enabled })
      setCreditRules((current) => current.map((item) => (item.action === updated.action ? updated : item)))
      await loadAuditLogs()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update credit rule')
    } finally {
      setWorking(false)
    }
  }

  async function saveProviderConfig(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault()
    setWorking(true)
    setError(null)
    try {
      await api.saveAdminProviderConfig({
        id: editingProviderConfigId,
        provider: providerType,
        name: providerName,
        model: providerModel,
        base_url: providerBaseUrl,
        api_key: providerApiKey || undefined,
        status: providerStatus,
      })
      setEditingProviderConfigId(undefined)
      setProviderApiKey('')
      await Promise.all([loadAdminSettings(), loadAuditLogs()])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save provider config')
    } finally {
      setWorking(false)
    }
  }

  function formatDuration(ms: number): string {
    if (!ms) return 'not finished'
    const seconds = Math.max(1, Math.round(ms / 1000))
    if (seconds < 60) return `${seconds}s`
    const minutes = Math.floor(seconds / 60)
    const rest = seconds % 60
    return rest ? `${minutes}m ${rest}s` : `${minutes}m`
  }

  return (
    <section className="admin-panel">
      <header className="admin-header">
        <div>
          <span className="eyebrow compact">
            <Shield size={14} />
            Admin
          </span>
          <h2>Users</h2>
        </div>
        <div className="admin-actions">
          <button className="secondary-button compact-button" type="button" onClick={() => void loadUsers()}>
            {loading ? <Loader2 className="spin" size={16} /> : <RefreshCw size={16} />}
            Refresh
          </button>
          <button className="secondary-button compact-button" type="button" onClick={onClose}>
            Back
          </button>
        </div>
      </header>

      <form className="admin-search" onSubmit={handleSearch}>
        <input value={query} placeholder="Search email" onChange={(event) => setQuery(event.target.value)} />
        <button type="submit" disabled={loading}>
          <Search size={17} />
          Search
        </button>
      </form>

      {error ? <p className="error-text">{error}</p> : null}

      {dashboard ? (
        <div className="admin-stat-grid">
          <article>
            <span>Users</span>
            <strong>{dashboard.users.total ?? 0}</strong>
            <small>{dashboard.users.active ?? 0} active</small>
          </article>
          <article>
            <span>Projects</span>
            <strong>{dashboard.projects.total ?? 0}</strong>
            <small>{dashboard.generation_runs.total ?? 0} generations</small>
          </article>
          <article>
            <span>Credits</span>
            <strong>{dashboard.credits.total_balance ?? 0}</strong>
            <small>current balance pool</small>
          </article>
        </div>
      ) : null}

      <div className="admin-grid">
        <aside className="admin-user-list">
          {users.map((user) => (
            <button
              className={`admin-user-row ${selectedUser?.id === user.id ? 'active' : ''}`}
              key={user.id}
              type="button"
              onClick={() => setSelectedUserId(user.id)}
            >
              <span>
                <strong>{user.email}</strong>
                <small>{user.status} · {user.role}</small>
              </span>
              <em>{user.points_balance}</em>
            </button>
          ))}
          {!loading && !users.length ? <p className="muted-text">No users found.</p> : null}
        </aside>

        <section className="admin-detail">
          {selectedUser ? (
            <>
              <div className="admin-user-summary">
                <div>
                  <h3>{selectedUser.email}</h3>
                  <p>{selectedUser.session_count} projects · {selectedUser.generation_count} generations</p>
                </div>
                <strong>{selectedUser.points_balance} points</strong>
              </div>

              <div className="admin-command-row">
                <button
                  className="secondary-button compact-button"
                  type="button"
                  disabled={working}
                  onClick={() => void updateUser({ status: selectedUser.status === 'active' ? 'disabled' : 'active' })}
                >
                  {selectedUser.status === 'active' ? <Ban size={16} /> : <CheckCircle2 size={16} />}
                  {selectedUser.status === 'active' ? 'Disable' : 'Enable'}
                </button>
                <button
                  className="secondary-button compact-button"
                  type="button"
                  disabled={working}
                  onClick={() => void updateUser({ role: selectedUser.role === 'admin' ? 'user' : 'admin' })}
                >
                  <UserCog size={16} />
                  {selectedUser.role === 'admin' ? 'Make user' : 'Make admin'}
                </button>
              </div>

              <form className="admin-credit-form" onSubmit={adjustCredits}>
                <label>
                  Amount
                  <input
                    type="number"
                    value={creditAmount}
                    onChange={(event) => setCreditAmount(Number(event.target.value))}
                  />
                </label>
                <label>
                  Reason
                  <input value={creditReason} onChange={(event) => setCreditReason(event.target.value)} />
                </label>
                <button type="submit" disabled={working || creditAmount === 0}>
                  {working ? <Loader2 className="spin" size={17} /> : <Coins size={17} />}
                  Adjust
                </button>
              </form>

              <div className="admin-columns">
                <AdminList title="Credit ledger">
                  {credits.map((entry) => (
                    <li key={entry.id}>
                      <strong>{entry.amount > 0 ? '+' : ''}{entry.amount}</strong>
                      <span>{entry.reason} · balance {entry.balance_after}</span>
                    </li>
                  ))}
                </AdminList>
                <AdminList title="Projects">
                  {sessions.map((session) => (
                    <li key={session.id}>
                      <strong>{session.topic}</strong>
                      <span>{session.status} · {session.slide_count} slides</span>
                    </li>
                  ))}
                </AdminList>
              </div>

              <div className="admin-run-card">
                <div className="admin-run-header">
                  <h4>Generation runs</h4>
                  <div className="admin-run-tools">
                    <select value={runStatus} onChange={(event) => setRunStatus(event.target.value)}>
                      <option value="queued">Queued</option>
                      <option value="running">Running</option>
                      <option value="failed">Failed</option>
                      <option value="cancelled">Cancelled</option>
                      <option value="completed">Completed</option>
                      <option value="all">All</option>
                    </select>
                    <button
                      className="secondary-button compact-button"
                      type="button"
                      disabled={working}
                      onClick={() => void loadRuns()}
                    >
                      <RefreshCw size={16} />
                      Refresh
                    </button>
                  </div>
                </div>
                {runMessage ? <p className="admin-run-message">{runMessage}</p> : null}
                <ul className="admin-run-list">
                  {runs.map((run) => (
                    <li key={run.id}>
                      <div>
                        <strong>{run.topic}</strong>
                        <span>
                          {run.status} · {run.progress}% · {run.page_count} pages · {formatDuration(run.duration_ms)} · {run.user_email ?? 'anonymous'}
                        </span>
                        {run.failure_category ? (
                          <small>{run.failure_category}: {run.failure_title ?? run.error ?? 'failed'}</small>
                        ) : run.error ? (
                          <small>{run.error}</small>
                        ) : null}
                      </div>
                      <em>{run.charge_amount} pts {run.charge_settled ? 'charged' : 'pending'}</em>
                      {run.status === 'queued' || run.status === 'running' ? (
                        <button
                          className="secondary-button compact-button danger-inline"
                          type="button"
                          disabled={working}
                          onClick={() => void cancelRun(run)}
                        >
                          <Square size={15} />
                          Cancel
                        </button>
                      ) : null}
                    </li>
                  ))}
                  {!runs.length ? <li className="empty-row">No generation runs.</li> : null}
                </ul>
              </div>

              <AdminList title="Audit logs">
                {auditLogs.slice(0, 8).map((log) => (
                  <li key={log.id}>
                    <strong>{log.action}</strong>
                    <span>{log.target_type} · {log.target_id ?? 'none'}</span>
                  </li>
                ))}
              </AdminList>

              <div className="admin-settings-grid">
                <section className="admin-run-card">
                  <div className="admin-run-header">
                    <h4>
                      <Megaphone size={16} />
                      Announcements
                    </h4>
                  </div>
                  <form className="admin-stacked-form" onSubmit={saveAnnouncement}>
                    <input
                      value={announcementTitle}
                      placeholder="Title"
                      onChange={(event) => setAnnouncementTitle(event.target.value)}
                    />
                    <textarea
                      value={announcementBody}
                      placeholder="Announcement body"
                      onChange={(event) => setAnnouncementBody(event.target.value)}
                    />
                    <select value={announcementStatus} onChange={(event) => setAnnouncementStatus(event.target.value)}>
                      <option value="draft">Draft</option>
                      <option value="published">Published</option>
                      <option value="archived">Archived</option>
                    </select>
                    <button type="submit" disabled={working || !announcementTitle.trim() || !announcementBody.trim()}>
                      {editingAnnouncementId ? 'Update announcement' : 'Save announcement'}
                    </button>
                    {editingAnnouncementId ? (
                      <button
                        className="secondary-button"
                        type="button"
                        onClick={() => {
                          setEditingAnnouncementId(undefined)
                          setAnnouncementTitle('')
                          setAnnouncementBody('')
                          setAnnouncementStatus('draft')
                        }}
                      >
                        New announcement
                      </button>
                    ) : null}
                  </form>
                  <ul className="admin-compact-list">
                    {announcements.slice(0, 6).map((announcement) => (
                      <li key={announcement.id}>
                        <strong>{announcement.title}</strong>
                        <span>{announcement.status} · {announcement.updated_at}</span>
                        <button
                          className="secondary-button compact-button"
                          type="button"
                          onClick={() => {
                            setEditingAnnouncementId(announcement.id)
                            setAnnouncementTitle(announcement.title)
                            setAnnouncementBody(announcement.body)
                            setAnnouncementStatus(announcement.status)
                          }}
                        >
                          Edit
                        </button>
                      </li>
                    ))}
                    {!announcements.length ? <li>No announcements.</li> : null}
                  </ul>
                </section>

                <section className="admin-run-card">
                  <div className="admin-run-header">
                    <h4>
                      <Coins size={16} />
                      Credit rules
                    </h4>
                  </div>
                  <ul className="admin-rule-list">
                    {creditRules.map((rule) => (
                      <li key={rule.action}>
                        <div>
                          <strong>{rule.label}</strong>
                          <span>{rule.description}</span>
                        </div>
                        <input
                          type="number"
                          min={0}
                          value={rule.amount}
                          onChange={(event) => {
                            const amount = Number(event.target.value)
                            setCreditRules((current) =>
                              current.map((item) =>
                                item.action === rule.action ? { ...item, amount } : item,
                              ),
                            )
                          }}
                        />
                        <label className="inline-check">
                          <input
                            type="checkbox"
                            checked={rule.enabled}
                            onChange={(event) =>
                              void updateRule(rule, rule.amount, event.target.checked)
                            }
                          />
                          enabled
                        </label>
                        <button
                          className="secondary-button compact-button"
                          type="button"
                          disabled={working}
                          onClick={() => void updateRule(rule, rule.amount, rule.enabled)}
                        >
                          Save
                        </button>
                      </li>
                    ))}
                  </ul>
                </section>

                <section className="admin-run-card">
                  <div className="admin-run-header">
                    <h4>
                      <KeyRound size={16} />
                      Provider configs
                    </h4>
                  </div>
                  <form className="admin-stacked-form" onSubmit={saveProviderConfig}>
                    <select value={providerType} onChange={(event) => setProviderType(event.target.value as 'llm' | 'ai_image')}>
                      <option value="llm">LLM</option>
                      <option value="ai_image">AI image</option>
                    </select>
                    <input value={providerName} placeholder="Name" onChange={(event) => setProviderName(event.target.value)} />
                    <input value={providerModel} placeholder="Model" onChange={(event) => setProviderModel(event.target.value)} />
                    <input value={providerBaseUrl} placeholder="Base URL" onChange={(event) => setProviderBaseUrl(event.target.value)} />
                    <input value={providerApiKey} placeholder="API key, leave empty to keep existing when editing later" onChange={(event) => setProviderApiKey(event.target.value)} />
                    <select value={providerStatus} onChange={(event) => setProviderStatus(event.target.value)}>
                      <option value="disabled">Disabled</option>
                      <option value="active">Active</option>
                    </select>
                    <button type="submit" disabled={working || !providerModel.trim()}>
                      {editingProviderConfigId ? 'Update provider' : 'Save provider'}
                    </button>
                    {editingProviderConfigId ? (
                      <button
                        className="secondary-button"
                        type="button"
                        onClick={() => {
                          setEditingProviderConfigId(undefined)
                          setProviderApiKey('')
                          setProviderType('llm')
                          setProviderName('OpenAI compatible')
                          setProviderModel('')
                          setProviderBaseUrl('')
                          setProviderStatus('disabled')
                        }}
                      >
                        New provider
                      </button>
                    ) : null}
                  </form>
                  <ul className="admin-compact-list">
                    {providerConfigs.map((config) => (
                      <li key={config.id}>
                        <strong>{config.provider} · {config.model}</strong>
                        <span>{config.status} · {config.api_key_masked || 'no key'}</span>
                        <button
                          className="secondary-button compact-button"
                          type="button"
                          onClick={() => {
                            setEditingProviderConfigId(config.id)
                            setProviderType(config.provider)
                            setProviderName(config.name)
                            setProviderModel(config.model)
                            setProviderBaseUrl(config.base_url ?? '')
                            setProviderStatus(config.status)
                            setProviderApiKey('')
                          }}
                        >
                          Edit
                        </button>
                      </li>
                    ))}
                    {!providerConfigs.length ? <li>No provider configs.</li> : null}
                  </ul>
                </section>
              </div>
            </>
          ) : (
            <p className="muted-text">Select a user to manage.</p>
          )}
        </section>
      </div>
    </section>
  )
}

function AdminList({
  title,
  children,
}: {
  title: string
  children: React.ReactNode
}): React.JSX.Element {
  return (
    <div className="admin-list-card">
      <h4>{title}</h4>
      <ul>{children}</ul>
    </div>
  )
}

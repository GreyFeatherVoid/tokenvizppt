import { FormEvent, useEffect, useMemo, useState } from 'react'
import { Ban, CheckCircle2, Coins, Loader2, RefreshCw, Search, Shield, UserCog } from 'lucide-react'
import {
  api,
  type AdminAuditLog,
  type AdminSessionSummary,
  type AdminUser,
  type CreditHistoryEntry,
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
  const [auditLogs, setAuditLogs] = useState<AdminAuditLog[]>([])
  const [creditAmount, setCreditAmount] = useState(30)
  const [creditReason, setCreditReason] = useState('Manual adjustment')

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

  useEffect(() => {
    void loadUsers()
    void loadAuditLogs()
  }, [])

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

              <AdminList title="Audit logs">
                {auditLogs.slice(0, 8).map((log) => (
                  <li key={log.id}>
                    <strong>{log.action}</strong>
                    <span>{log.target_type} · {log.target_id ?? 'none'}</span>
                  </li>
                ))}
              </AdminList>
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

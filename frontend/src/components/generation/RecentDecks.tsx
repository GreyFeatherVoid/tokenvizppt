import { ChevronLeft, ChevronRight, Clock3, Trash2 } from 'lucide-react'
import { useState } from 'react'
import type { SessionSummary } from '../../lib/api'
import { useI18n } from '../../i18n'

interface RecentDecksProps {
  sessions: SessionSummary[]
  loading: boolean
  activeSessionId: string | null
  onOpen: (sessionId: string) => Promise<void>
  onDelete: (sessionId: string) => Promise<void>
}

export function RecentDecks({
  sessions,
  loading,
  activeSessionId,
  onOpen,
  onDelete,
}: RecentDecksProps): React.JSX.Element {
  const [open, setOpen] = useState(false)
  const { t } = useI18n()

  return (
    <aside className={open ? 'recent-sidebar open' : 'recent-sidebar'}>
      <section className="recent-card" aria-hidden={!open}>
        <div className="recent-header">
          <div>
            <span className="eyebrow compact">
              <Clock3 size={14} />
              {t('recentDecks')}
            </span>
            <h2>{t('savedLocally')}</h2>
          </div>
          {loading ? <small>{t('loading')}</small> : <small>{sessions.length} {t('records')}</small>}
        </div>
        {!loading && !sessions.length ? (
          <p className="muted-text">{t('noSavedDecks')}</p>
        ) : null}
        {sessions.length ? (
          <div className="recent-list">
            {sessions.map((session) => (
              <article
                className={session.id === activeSessionId ? 'recent-item active' : 'recent-item'}
                key={session.id}
              >
                <button
                  className="recent-open"
                  type="button"
                  onClick={() => {
                    void onOpen(session.id)
                  }}
                >
                  <strong>{session.topic}</strong>
                  <span>{session.brief}</span>
                  <small>
                    {session.status} · {session.slide_count || session.page_count} {t('slidesUnit')} ·{' '}
                    {session.style_id} · {languageLabel(session.output_language)} · {t('updated')}{' '}
                    {formatDate(session.updated_at)}
                  </small>
                </button>
                <button
                  aria-label={`Delete ${session.topic}`}
                  className="icon-button danger"
                  type="button"
                  onClick={() => {
                    if (
                      window.confirm(
                        `${t('deleteConfirmPrefix')} "${session.topic}"? ${t('deleteConfirmSuffix')}`,
                      )
                    ) {
                      void onDelete(session.id)
                    }
                  }}
                >
                  <Trash2 size={16} />
                </button>
              </article>
            ))}
          </div>
        ) : null}
      </section>
      <button
        className="recent-toggle"
        type="button"
        onClick={() => setOpen((current) => !current)}
      >
        {open ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
        <Clock3 size={16} />
        <span>{open ? t('hideHistory') : t('history')}</span>
      </button>
    </aside>
  )
}

function languageLabel(value: string): string {
  if (value === 'zh-CN') return '中文'
  if (value === 'en-US') return 'English'
  return 'Auto'
}

function formatDate(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString()
}

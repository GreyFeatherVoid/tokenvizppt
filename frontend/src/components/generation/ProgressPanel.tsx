import type { GenerationEvent } from '../../lib/api'
import { useI18n } from '../../i18n'
import { WaitingGames } from './WaitingGames'

interface ProgressPanelProps {
  events: GenerationEvent[]
  latestProgress: number
  sessionId: string | null
  loading?: boolean
  completed?: boolean
  onViewDeck?: () => void
  onEnableNotifications?: () => void
  notificationAvailable?: boolean
}

export function ProgressPanel({
  events,
  latestProgress,
  sessionId,
  loading = false,
  completed = false,
  onViewDeck,
  onEnableNotifications,
  notificationAvailable = false,
}: ProgressPanelProps): React.JSX.Element {
  const { t } = useI18n()
  const gameVisible = latestProgress > 0 || completed
  const hasEvents = events.length > 0
  const statusLabel = completed
    ? t('completedStatus')
    : events.some((event) => event.type === 'running' || event.progress >= 3)
      ? t('runningStatus')
      : loading || events.some((event) => event.type === 'queued')
        ? t('queuedStatus')
        : hasEvents
          ? t('queuedStatus')
          : t('readyStatus')

  return (
    <aside className="progress-card">
      <div className="progress-header">
        <span>{t('generationProgress')}</span>
        <div className="progress-status">
          <em>{statusLabel}</em>
          <strong>{latestProgress}%</strong>
        </div>
      </div>
      <div className="progress-track">
        <div className="progress-fill" style={{ width: `${latestProgress}%` }} />
      </div>
      {sessionId ? <p className="meta">Session: {sessionId}</p> : null}
      {notificationAvailable && onEnableNotifications && !completed ? (
        <button className="secondary-button notification-button" type="button" onClick={onEnableNotifications}>
          {t('notificationEnable')}
        </button>
      ) : null}
      {completed ? (
        <div className="generation-complete-callout">
          <strong>{t('generationComplete')}</strong>
          <p>{t('generationCompleteHint')}</p>
          <button type="button" onClick={onViewDeck}>
            {t('viewGeneratedDeck')}
          </button>
        </div>
      ) : null}
      <div className="event-log">
        {events.length === 0 ? (
          <p className="muted">{t('progressEmpty')}</p>
        ) : (
          events.map((item, index) => (
            <div key={`${item.progress}-${index}`} className="event-row">
              <span>{item.progress}%</span>
              <p>{item.message}</p>
            </div>
          ))
        )}
      </div>
      {gameVisible ? <WaitingGames /> : null}
    </aside>
  )
}

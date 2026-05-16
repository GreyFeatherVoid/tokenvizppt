import type { GenerationEvent } from '../../lib/api'
import { useI18n } from '../../i18n'
import { WaitingGames } from './WaitingGames'

interface ProgressPanelProps {
  events: GenerationEvent[]
  latestProgress: number
  sessionId: string | null
  completed?: boolean
  onViewDeck?: () => void
}

export function ProgressPanel({
  events,
  latestProgress,
  sessionId,
  completed = false,
  onViewDeck,
}: ProgressPanelProps): React.JSX.Element {
  const { t } = useI18n()
  const gameVisible = latestProgress > 0 || completed

  return (
    <aside className="progress-card">
      <div className="progress-header">
        <span>{t('generationProgress')}</span>
        <strong>{latestProgress}%</strong>
      </div>
      <div className="progress-track">
        <div className="progress-fill" style={{ width: `${latestProgress}%` }} />
      </div>
      {sessionId ? <p className="meta">Session: {sessionId}</p> : null}
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

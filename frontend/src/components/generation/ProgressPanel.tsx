import type { GenerationEvent } from '../../lib/api'

interface ProgressPanelProps {
  events: GenerationEvent[]
  latestProgress: number
  sessionId: string | null
}

export function ProgressPanel({
  events,
  latestProgress,
  sessionId,
}: ProgressPanelProps): React.JSX.Element {
  return (
    <aside className="progress-card">
      <div className="progress-header">
        <span>Generation progress</span>
        <strong>{latestProgress}%</strong>
      </div>
      <div className="progress-track">
        <div className="progress-fill" style={{ width: `${latestProgress}%` }} />
      </div>
      {sessionId ? <p className="meta">Session: {sessionId}</p> : null}
      <div className="event-log">
        {events.length === 0 ? (
          <p className="muted">Progress events will appear here.</p>
        ) : (
          events.map((item, index) => (
            <div key={`${item.progress}-${index}`} className="event-row">
              <span>{item.progress}%</span>
              <p>{item.message}</p>
            </div>
          ))
        )}
      </div>
    </aside>
  )
}

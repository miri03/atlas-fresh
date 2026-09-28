import type { ReactNode } from 'react'
import type { ClientStatusKind, Segment } from '../types'

export function SegmentDot({ segment }: { segment: Segment }) {
  return <span className={`dot dot-${segment.toLowerCase()}`} aria-hidden="true" title={segment} />
}

export function StatusChip({ status }: { status: ClientStatusKind }) {
  return <span className={`chip chip-${status.toLowerCase()}`}>{status}</span>
}

export function ReasonTag({ reason }: { reason: string | null }) {
  if (!reason) return <span className="reason-none">—</span>
  const label = reason === 'STATION_CAPACITY_REACHED' ? 'Station capacity' : 'Segment shortage'
  return (
    <span className={`chip chip-reason chip-reason-${reason === 'STATION_CAPACITY_REACHED' ? 'capacity' : 'segment'}`}>
      {label}
    </span>
  )
}

export function MetricCard({
  label,
  value,
  sub,
  tone = 'neutral',
  hint,
  id,
}: {
  label: string
  value: string
  sub?: string
  tone?: 'neutral' | 'good' | 'warn' | 'bad' | 'brand'
  hint?: string
  id?: string
}) {
  return (
    <div className={`metric metric-${tone}`} id={id}>
      <div className="metric-label">{label}</div>
      <div className="metric-value">{value}</div>
      {sub && <div className="metric-sub">{sub}</div>}
      {hint && <div className="metric-hint">{hint}</div>}
    </div>
  )
}

export function Section({
  title,
  id,
  subtitle,
  actions,
  children,
}: {
  title: string
  id?: string
  subtitle?: string
  actions?: ReactNode
  children: ReactNode
}) {
  return (
    <section className="section" id={id} aria-labelledby={id ? `${id}-h` : undefined}>
      <header className="section-head">
        <div>
          <h2 id={id ? `${id}-h` : undefined}>{title}</h2>
          {subtitle && <p className="section-sub">{subtitle}</p>}
        </div>
        {actions && <div className="section-actions">{actions}</div>}
      </header>
      {children}
    </section>
  )
}

export function ErrorBanner({ message, issues, onRetry }: { message: string; issues?: { location: string; message: string }[]; onRetry?: () => void }) {
  return (
    <div className="error-banner" role="alert" aria-live="assertive">
      <div className="error-title">Could not complete the step</div>
      <p className="error-message">{message}</p>
      {issues && issues.length > 0 && (
        <ul className="error-issues">
          {issues.map((i, idx) => (
            <li key={idx}>
              <code>{i.location}</code> — {i.message}
            </li>
          ))}
        </ul>
      )}
      {onRetry && (
        <button className="btn btn-secondary" onClick={onRetry}>
          Try again
        </button>
      )}
    </div>
  )
}

export function Spinner({ label }: { label: string }) {
  return (
    <div className="spinner" role="status" aria-live="polite">
      <span className="spinner-bar" aria-hidden="true" />
      <span>{label}</span>
    </div>
  )
}

export function Empty({ label }: { label: string }) {
  return <div className="empty">{label}</div>
}

export const money = (n: number) => `€${n.toLocaleString('en-US', { maximumFractionDigits: 0 })}`
export const tonnes = (n: number) => `${n.toLocaleString('en-US', { maximumFractionDigits: 1 })} t`
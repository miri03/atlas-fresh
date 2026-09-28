import type { DataHealth, KpiReport } from '../types'
import { SegmentDot } from './ui'

const SEGMENTS = ['A', 'B', 'C', 'D'] as const
const PALETTE: Record<string, string> = { A: '#2f6f3d', B: '#4c8c4f', C: '#8fae3a', D: '#c8a93e' }
const EMPTY = '#e2e0d8'
const BAR_HEIGHT = 22
const GAP = 10
const LABEL_W = 100
const VALUE_W = 92
const CHART_W = 560

export function SegmentChart({
  health,
  showLegend = true,
}: {
  health: DataHealth
  showLegend?: boolean
}) {
  const max = Math.max(...SEGMENTS.map((s) => Math.max(health.expected_by_segment_t[s], health.actual_by_segment_t[s]))) * 1.1
  const plotW = CHART_W - LABEL_W - VALUE_W
  const scale = (v: number) => (v / max) * plotW
  const groups = SEGMENTS.map((s) => {
    const e = health.expected_by_segment_t[s]
    const a = health.actual_by_segment_t[s]
    const d = a - e
    return { s, e, a, d }
  })

  return (
    <div className="segment-chart">
      <svg
        viewBox={`0 0 ${CHART_W} ${groups.length * (BAR_HEIGHT * 2 + GAP)}`}
        width="100%"
        role="img"
        aria-label="Expected vs actual tonnes by quality segment"
      >
        {groups.map((g, i) => {
          const y = i * (BAR_HEIGHT * 2 + GAP)
          const diff = g.d > 0 ? `+${g.d.toFixed(1)}` : g.d.toFixed(1)
          return (
            <g key={g.s}>
              <text x={0} y={y + BAR_HEIGHT * 0.5 + 6} className="chart-label" textAnchor="start">
                <tspan fontWeight="700">{g.s}</tspan> {diff} t
              </text>
              <rect
                x={LABEL_W}
                y={y}
                width={scale(g.e)}
                height={BAR_HEIGHT}
                fill={EMPTY}
                rx={3}
                aria-hidden="true"
              />
              <text x={LABEL_W + scale(g.e) + 4} y={y + BAR_HEIGHT * 0.5 + 5} className="chart-bar-label">
                plan {g.e.toFixed(1)}
              </text>
              <rect
                x={LABEL_W}
                y={y + BAR_HEIGHT + 4}
                width={scale(g.a)}
                height={BAR_HEIGHT}
                fill={PALETTE[g.s]}
                rx={3}
                aria-hidden="true"
              />
              <text x={LABEL_W + scale(g.a) + 4} y={y + BAR_HEIGHT + BAR_HEIGHT * 0.5 + 9} className="chart-bar-label">
                actual {g.a.toFixed(1)}
              </text>
            </g>
          )
        })}
      </svg>
      {showLegend && (
        <div className="legend">
          <span className="legend-item"><span className="legend-swatch" style={{ background: '#e2e0d8' }} /> expected</span>
          <span className="legend-item"><span className="legend-swatch" style={{ background: PALETTE.A }} /> actual</span>
        </div>
      )}
    </div>
  )
}

export function CapacityChart({ kpis }: { kpis: KpiReport }) {
  const total = Math.max(kpis.actual_received_t, kpis.station_capacity_t)
  const capacity = kpis.station_capacity_t
  return (
    <div className="capacity-chart">
      <div
        className="capacity-track"
        role="img"
        aria-label={`${kpis.export_t} t exported out of ${capacity} t station capacity; ${kpis.local_t} t local`}
      >
        <div className="capacity-fill" style={{ width: `${(kpis.export_t / total) * 100}%` }} />
        <div
          className="capacity-limit"
          style={{ left: `${(capacity / total) * 100}%` }}
          title={`Station capacity ${capacity} t`}
        />
        <div
          className="capacity-local"
          style={{
            left: `${(kpis.export_t / total) * 100}%`,
            width: `${(kpis.local_t / total) * 100}%`,
          }}
        />
      </div>
      <div className="capacity-labels">
        <span>
          <span className="legend-swatch" style={{ background: 'var(--c-brand)' }} /> exported {kpis.export_t.toFixed(0)} t
        </span>
        <span>
          <span className="legend-swatch" style={{ background: 'var(--c-danger)' }} /> local {kpis.local_t.toFixed(0)} t
        </span>
        <span>
          <span className="legend-swatch legend-line" /> station capacity {capacity.toFixed(0)} t
        </span>
      </div>
    </div>
  )
}

export function SegmentPills({ segments }: { segments: Partial<Record<string, number>> }) {
  return (
    <span className="segment-pills">
      {SEGMENTS.map((s) => (
        <span key={s} className="segment-pill">
          <SegmentDot segment={s} />
          <span className="segment-pill-count">{segments[s] ?? 0}</span> t
        </span>
      ))}
    </span>
  )
}
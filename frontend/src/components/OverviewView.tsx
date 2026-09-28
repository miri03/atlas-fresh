import type { PlanResult } from '../types'
import { CapacityChart, SegmentChart } from './charts'
import { Section, SegmentDot, StatusChip } from './ui'

function topGaps(plan: PlanResult, direction: 'below' | 'above', n = 4) {
  const list = plan.farm_comparisons
    .flatMap((f) =>
      f.segment_variances.map((v) => ({
        farm_id: f.farm_id,
        farm_name: f.farm_name,
        segment: v.segment,
        variance: v.variance_t,
      })),
    )
    .filter((v) => (direction === 'below' ? v.variance <= -5 : v.variance >= 5))
    .sort((x, y) => Math.abs(y.variance) - Math.abs(x.variance))
  return list.slice(0, n)
}

function headlineInsight(plan: PlanResult): string[] {
  const lines: string[] = []
  const { expected_by_segment_t, actual_by_segment_t } = plan.data_health
  const aShortfall = expected_by_segment_t.A - actual_by_segment_t.A
  if (aShortfall >= 5) lines.push(`Segment A — the hardest quality to produce — arrived ${aShortfall.toFixed(1)} t below plan.`)
  const netShortfall = plan.kpis.expected_plan_t - plan.kpis.actual_received_t
  lines.push(`Farm receipts total ${plan.kpis.actual_received_t} t against ${plan.kpis.expected_plan_t} t planned — ${Math.abs(netShortfall).toFixed(1)} t below plan for the day.`)
  const partial = plan.client_statuses.filter((c) => c.status === 'PARTIAL')
  const unserved = plan.client_statuses.filter((c) => c.status === 'UNSERVED')
  if (partial.length) {
    const bySegment = partial.filter((c) => c.shortage_reason === 'INSUFFICIENT_COMPATIBLE_SEGMENT')
    const byCapacity = partial.filter((c) => c.shortage_reason === 'STATION_CAPACITY_REACHED')
    if (bySegment.length)
      lines.push(`${bySegment.map((c) => c.client_id).join(', ')} are only partially served — not enough compatible segment supply on hand.`)
    if (byCapacity.length)
      lines.push(`${byCapacity.map((c) => c.client_id).join(', ')} is capped by the ${plan.kpis.station_capacity_t} t station limit.`)
  }
  if (unserved.length) lines.push(`${unserved.map((c) => c.client_id).join(', ')} could not be served at all today.`)
  if (plan.kpis.local_t > 0) lines.push(`${plan.kpis.local_t.toFixed(0)} t fall to the local market worth €${plan.kpis.local_value_eur.toLocaleString()} — ${plan.kpis.export_rate_pct}% of the crop is exported.`)
  return lines
}

export function OverviewView({ plan }: { plan: PlanResult }) {
  const gaps = topGaps(plan, 'below', 4)
  const surplus = topGaps(plan, 'above', 3)
  const insights = headlineInsight(plan)
  const shortfallA = gaps.filter((g) => g.segment === 'A')

  return (
    <>
      <Section
        title="Today at a glance"
        subtitle="The committee decides today's farm-to-client export plan from actual receipts."
      >
        <ul className="insights" aria-label="What happened today">
          {insights.map((line, i) => (
            <li key={i}>{line}</li>
          ))}
        </ul>
      </Section>

      <div className="two-col">
        <Section title="Expected vs actual by segment" subtitle="Production compare: plan against actual receipts.">
          <SegmentChart health={plan.data_health} />
        </Section>
        <Section title="Exported vs local residual" subtitle="Station execution and the value left on the local market.">
          <CapacityChart kpis={plan.kpis} />
          <div className="kv-list">
            <div><span>Station capacity</span><strong>{plan.kpis.station_capacity_t.toFixed(0)} t</strong></div>
            <div><span>Exported</span><strong>{plan.kpis.export_t.toFixed(0)} t</strong></div>
            <div><span>Local (10% of segment reference)</span><strong>€{plan.kpis.local_value_eur.toLocaleString()}</strong></div>
            <div><span>Export revenue</span><strong>€{plan.kpis.export_revenue_eur.toLocaleString()}</strong></div>
            <div><span>Total value</span><strong>€{plan.kpis.total_value_eur.toLocaleString()}</strong></div>
          </div>
        </Section>
      </div>

      <div className="two-col">
        <Section title="Shortest today" subtitle="Farm-segments most below plan — the reason exports run short.">
          <ul className="gap-list">
            {gaps.map((g) => (
              <li key={`${g.farm_id}-${g.segment}`}>
                <span className="gap-farm"><code>{g.farm_id}</code> {g.farm_name}</span>
                <span className="gap-bar-wrap">
                  <span className="gap-bar gap-bar-below" style={{ width: `${Math.min(100, Math.abs(g.variance) * 3)}%` }} />
                </span>
                <span className="gap-delta below">{g.variance.toFixed(1)} t</span>
              </li>
            ))}
            {gaps.length === 0 && <li>No farm-segment is below plan today.</li>}
          </ul>
        </Section>
        <Section title="Above plan" subtitle="Segments that exceeded their expected mix today.">
          <ul className="gap-list">
            {surplus.map((g) => (
              <li key={`${g.farm_id}-${g.segment}`}>
                <span className="gap-farm"><code>{g.farm_id}</code> {g.farm_name}</span>
                <span className="gap-bar-wrap">
                  <span className="gap-bar gap-bar-above" style={{ width: `${Math.min(100, Math.abs(g.variance) * 3)}%` }} />
                </span>
                <span className="gap-delta above">+{g.variance.toFixed(1)} t</span>
              </li>
            ))}
            {surplus.length === 0 && <li>No farm-segment is above plan today.</li>}
          </ul>
          {shortfallA.length > 0 && (
            <div className="note note-warn">
              Segment A shortfall is the binding constraint: scarce high quality cannot be substituted upward.
            </div>
          )}
        </Section>
      </div>

      <Section title="Client orders at risk" subtitle="Commercial view: who is complete, partial or unserved — and why.">
        <table className="table table-clients">
          <thead>
            <tr>
              <th>Client</th>
              <th>Rule</th>
              <th>Demand</th>
              <th>Allocated</th>
              <th>Status</th>
              <th>Reason</th>
              <th className="num">Revenue</th>
            </tr>
          </thead>
          <tbody>
            {plan.client_statuses.map((c) => (
              <tr key={c.client_id} className={c.status !== 'COMPLETE' ? 'row-at-risk' : ''}>
                <td className="cell-primary">
                  <code>{c.client_id}</code> {c.client_name}
                </td>
                <td>
                  <span className="mode-chip mode-minimum">{c.acceptance_mode}</span>
                  <SegmentDot segment={c.requested_segment} /> {c.requested_segment}
                </td>
                <td className="num">{c.demand_t.toFixed(0)} t</td>
                <td className="num">{c.allocated_t.toFixed(0)} t</td>
                <td><StatusChip status={c.status} /></td>
                <td>{c.allocated_t < c.demand_t ? reasonText(c.shortage_reason) : <span className="reason-none">fully served</span>}</td>
                <td className="num">€{c.export_revenue_eur.toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Section>
    </>
  )
}

function reasonText(reason: string | null) {
  if (!reason) return null
  return reason === 'STATION_CAPACITY_REACHED' ? 'Station capacity reached' : 'Compatible segment supply exhausted'
}
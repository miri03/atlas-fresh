import { useMemo, useState } from 'react'
import type { PlanResult, Segment } from '../types'
import { money, Section, SegmentDot, tonnes } from './ui'

export function AllocationView({ plan }: { plan: PlanResult }) {
  const [query, setQuery] = useState('')
  const [showAll, setShowAll] = useState(true)

  const rows = useMemo(() => {
    const q = query.trim().toLowerCase()
    return plan.allocations.filter(
      (a) =>
        !q ||
        a.farm_id.toLowerCase().includes(q) ||
        a.client_id.toLowerCase().includes(q) ||
        a.farm_name.toLowerCase().includes(q) ||
        a.client_name.toLowerCase().includes(q),
    )
  }, [plan.allocations, query])

  const totalTonnes = plan.allocations.reduce((acc, a) => acc + a.tonnes, 0)
  const totalRev = plan.allocations.reduce((acc, a) => acc + a.export_revenue_eur, 0)

  const residualBySegment = useMemo(() => {
    const bySeg = new Map<Segment, { t: number; value: number }>()
    for (const r of plan.local_residuals) {
      const cur = bySeg.get(r.segment) ?? { t: 0, value: 0 }
      cur.t += r.local_t
      cur.value += r.local_value_eur
      bySeg.set(r.segment, cur)
    }
    return bySeg
  }, [plan.local_residuals])

  return (
    <div className="stack">
      <Section
        title="Allocation detail — traceable export plan"
        subtitle="Every exported tonne resolves to exactly one farm, one quality segment and one client. Quality upgrade is 0 when the client's exact segment is used, or the number of levels above what they asked for."
        actions={
          <input
            className="search-input"
            value={query}
            placeholder="Filter farm or client…"
            aria-label="Filter allocations"
            onChange={(e) => setQuery(e.target.value)}
          />
        }
      >
        <div className="allocation-summary" aria-label="Allocation totals">
          <span>{plan.allocations.length} allocation rows</span>
          <span>{tonnes(totalTonnes)} exported</span>
          <span>{money(totalRev)} export revenue</span>
        </div>
        <div className="table-scroll">
          <table className="table table-allocation">
            <thead>
              <tr>
                <th>Farm</th>
                <th>Segment</th>
                <th>Client</th>
                <th className="num">Tonnes</th>
                <th className="num">Upgrade</th>
                <th className="num">Export revenue</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((a, i) => (
                <tr key={`${a.farm_id}-${a.segment}-${a.client_id}-${i}`}>
                  <td className="cell-primary"><code>{a.farm_id}</code> {a.farm_name}</td>
                  <td><SegmentDot segment={a.segment} /> {a.segment}</td>
                  <td className="cell-primary"><code>{a.client_id}</code> {a.client_name}</td>
                  <td className="num">{a.tonnes.toFixed(0)}</td>
                  <td className="num">{a.quality_upgrade === 0 ? '—' : `+${a.quality_upgrade}`}</td>
                  <td className="num">{money(a.export_revenue_eur)}</td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr>
                <td colSpan={3}>Total shown</td>
                <td className="num"><strong>{rows.reduce((acc, a) => acc + a.tonnes, 0).toFixed(0)}</strong></td>
                <td />
                <td className="num"><strong>{money(rows.reduce((acc, a) => acc + a.export_revenue_eur, 0))}</strong></td>
              </tr>
            </tfoot>
          </table>
        </div>
        {rows.length === 0 && <p className="empty">No allocation matches the filter.</p>}
      </Section>

      <Section
        title="Local market residual"
        subtitle="Every actual tonne not exported falls back to the local market at 10% of its segment's reference export price. This is the cost of the volume the committee could not place."
        actions={
          <button className="btn btn-secondary" onClick={() => setShowAll((s) => !s)} aria-pressed={showAll}>
            {showAll ? 'Collapse' : 'Expand'} residual by farm
          </button>
        }
      >
        <div className="local-overview">
          {Array.from(residualBySegment.entries()).map(([seg, val]) => (
            <div key={seg} className="local-card">
              <div className="local-card-head"><SegmentDot segment={seg} /> Segment {seg}</div>
              <div className="local-card-value">{val.t.toFixed(0)} t</div>
              <div className="local-card-sub">{money(val.value)} at 10% of reference</div>
            </div>
          ))}
          {plan.local_residuals.length === 0 && (
            <p className="empty">Nothing goes to the local market today — the whole crop was exported.</p>
          )}
        </div>
        {showAll && plan.local_residuals.length > 0 && (
          <div className="table-scroll">
            <table className="table table-local">
              <thead>
                <tr>
                  <th>Farm</th>
                  <th>Segment</th>
                  <th className="num">Local tonnes</th>
                  <th className="num">Reference price</th>
                  <th className="num">Local value</th>
                </tr>
              </thead>
              <tbody>
                {plan.local_residuals.map((r) => (
                  <tr key={`${r.farm_id}-${r.segment}`}>
                    <td><code>{r.farm_id}</code> {farmName(plan, r.farm_id)}</td>
                    <td><SegmentDot segment={r.segment} /> {r.segment}</td>
                    <td className="num">{r.local_t.toFixed(0)}</td>
                    <td className="num">€{r.reference_price_per_t_eur.toLocaleString()}/t</td>
                    <td className="num delta-below">{money(r.local_value_eur)}</td>
                  </tr>
                ))}
                <tfoot>
                  <tr>
                    <td colSpan={2}>Total local residual</td>
                    <td className="num"><strong>{plan.kpis.local_t.toFixed(0)}</strong></td>
                    <td />
                    <td className="num"><strong>{money(plan.kpis.local_value_eur)}</strong></td>
                  </tr>
                </tfoot>
              </tbody>
            </table>
          </div>
        )}
      </Section>
    </div>
  )
}

function farmName(plan: PlanResult, id: string) {
  return plan.farm_comparisons.find((f) => f.farm_id === id)?.farm_name ?? ''
}
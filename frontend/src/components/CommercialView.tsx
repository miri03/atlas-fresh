import { useMemo, useState } from 'react'
import type { ClientStatus } from '../types'
import { Empty, ReasonTag, Section, SegmentDot, StatusChip } from './ui'

type Filter = 'ALL' | 'COMPLETE' | 'PARTIAL' | 'UNSERVED'

const FILTERS: Filter[] = ['ALL', 'COMPLETE', 'PARTIAL', 'UNSERVED']

export function CommercialView({ clients }: { clients: ClientStatus[] }) {
  const [filter, setFilter] = useState<Filter>('ALL')
  const [query, setQuery] = useState('')

  const rows = useMemo(() => {
    const q = query.trim().toLowerCase()
    return clients
      .filter((c) => filter === 'ALL' || c.status === filter)
      .filter((c) => !q || c.client_id.toLowerCase().includes(q) || c.client_name.toLowerCase().includes(q))
  }, [clients, filter, query])

  const counts = useMemo(
    () => ({
      ALL: clients.length,
      COMPLETE: clients.filter((c) => c.status === 'COMPLETE').length,
      PARTIAL: clients.filter((c) => c.status === 'PARTIAL').length,
      UNSERVED: clients.filter((c) => c.status === 'UNSERVED').length,
    }),
    [clients],
  )

  return (
    <Section
      title="Commercial — client orders"
      subtitle="Higher-priced orders are protected first. A client is complete, partial or unserved; every shortfall carries a reason."
      actions={<input className="search-input" value={query} placeholder="Filter client…" aria-label="Filter clients" onChange={(e) => setQuery(e.target.value)} />}
    >
      <div className="filter-row" role="group" aria-label="Filter by client status">
        {FILTERS.map((f) => (
          <button
            key={f}
            className={`btn btn-filter ${filter === f ? 'btn-filter-active' : ''}`}
            onClick={() => setFilter(f)}
            aria-pressed={filter === f}
          >
            {f} <span className="filter-count">{counts[f]}</span>
          </button>
        ))}
      </div>
      <div className="table-scroll">
        <table className="table table-clients">
          <thead>
            <tr>
              <th>Client</th>
              <th>Rule</th>
              <th>Demand</th>
              <th>Allocated</th>
              <th>Remaining</th>
              <th>Status</th>
              <th>Reason</th>
              <th className="num">Export revenue</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((c) => (
              <tr key={c.client_id} className={c.status !== 'COMPLETE' ? 'row-at-risk' : ''}>
                <td className="cell-primary">
                  <code>{c.client_id}</code> {c.client_name}
                </td>
                <td>
                  <span className={`mode-chip ${c.acceptance_mode === 'EXACT' ? 'mode-exact' : 'mode-minimum'}`}>
                    {c.acceptance_mode}
                  </span>{' '}
                  <SegmentDot segment={c.requested_segment} /> {c.requested_segment}
                </td>
                <td className="num">{c.demand_t.toFixed(0)} t</td>
                <td className="num"><strong>{c.allocated_t.toFixed(0)} t</strong></td>
                <td className="num">{c.remaining_t > 0 ? c.remaining_t.toFixed(0) : '—'}</td>
                <td><StatusChip status={c.status} /></td>
                <td><ReasonTag reason={c.shortage_reason} /></td>
                <td className="num">€{c.export_revenue_eur.toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {rows.length === 0 && <Empty label="No client matches the filter." />}
    </Section>
  )
}
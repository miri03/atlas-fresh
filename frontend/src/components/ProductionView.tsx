import { useMemo, useState } from 'react'
import type { FarmComparison, Segment } from '../types'
import { Empty, Section, SegmentDot } from './ui'

const SEGMENTS: Segment[] = ['A', 'B', 'C', 'D']

type SortKey = 'farm_id' | 'capacity_variance'

export function farmDelta(f: FarmComparison, seg: Segment): number {
  return f.segment_variances.find((v) => v.segment === seg)?.variance_t ?? 0
}

export function ProductionView({ farms }: { farms: FarmComparison[] }) {
  const [query, setQuery] = useState('')
  const [sort, setSort] = useState<SortKey>('farm_id')
  const [dir, setDir] = useState<'asc' | 'desc'>('asc')

  const rows = useMemo(() => {
    const q = query.trim().toLowerCase()
    const filtered = farms.filter(
      (f) => !q || f.farm_id.toLowerCase().includes(q) || f.farm_name.toLowerCase().includes(q),
    )
    const delta = dir === 'asc' ? 1 : -1
    return [...filtered].sort((a, b) => {
      if (sort === 'farm_id') return a.farm_id.localeCompare(b.farm_id, undefined, { numeric: true }) * delta
      return (a.capacity_variance_t - b.capacity_variance_t) * delta
    })
  }, [farms, query, sort, dir])

  const toggleSort = (next: SortKey) => {
    if (next === sort) setDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    else {
      setSort(next)
      setDir('asc')
    }
  }

  return (
    <Section
      title="Production — plan vs actual by farm"
      subtitle="Expected capacity and mix come from the season plan. Actual A/B/C/D tonnes are today's real receipts — they are the only supply that can be exported. Planned values are for comparison, never for allocation."
      actions={
        <div className="search-box">
          <span className="search-field">
            <span className="search-icon" aria-hidden="true" />
            <span className="visually-hidden">Filter farms</span>
            <input
              className="search-input"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Filter farm ID or name…"
              aria-label="Filter farms by ID or name"
            />
          </span>
          {query && (
            <button className="search-clear" onClick={() => setQuery('')} aria-label="Clear farm filter">
              Clear
            </button>
          )}
          <span className="search-count" aria-live="polite">
            {rows.length}/{farms.length} farms
          </span>
        </div>
      }
    >
      <div className="table-scroll">
        <table className="table table-farms">
          <thead>
            <tr>
              <th aria-sort={sort === 'farm_id' ? (dir === 'asc' ? 'ascending' : 'descending') : 'none'}>
                <button className="th-sort" onClick={() => toggleSort('farm_id')}>Farm</button>
              </th>
              <th className="num">Plan cap.</th>
              <th className="num">Actual</th>
              <th aria-sort={sort === 'capacity_variance' ? (dir === 'asc' ? 'ascending' : 'descending') : 'none'}>
                <button className="th-sort" onClick={() => toggleSort('capacity_variance')}>Δ volume</button>
              </th>
              <th>Segment variance (expected → actual)</th>
              <th className="num">Exported</th>
              <th className="num">Local</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((f) => {
              const below = f.capacity_variance_t < 0
              return (
                <tr key={f.farm_id}>
                  <td className="cell-primary">
                    <code>{f.farm_id}</code> {f.farm_name}
                  </td>
                  <td className="num">{f.expected_capacity_t.toFixed(1)} t</td>
                  <td className="num"><strong>{f.actual_total_t.toFixed(1)} t</strong></td>
                  <td className={`num ${below ? 'delta-below' : f.capacity_variance_t > 0 ? 'delta-above' : ''}`}>
                    {f.capacity_variance_t > 0 ? `+${f.capacity_variance_t.toFixed(1)}` : f.capacity_variance_t.toFixed(1)}
                  </td>
                  <td>
                    <div className="seg-stack">
                      {SEGMENTS.map((s) => {
                        const d = farmDelta(f, s)
                        const expected = f.segment_variances.find((v) => v.segment === s)!.expected_t
                        const actual = f.segment_variances.find((v) => v.segment === s)!.actual_t
                        return (
                          <div className="seg-row" key={s}>
                            <span className="seg-name"><SegmentDot segment={s} /> {s}</span>
                            <span className={`seg-variance ${d < 0 ? 'below' : d > 0 ? 'above' : ''}`}>
                              {d > 0 ? `+${Math.round(d)}` : Math.round(d)}
                            </span>
                            <span className="seg-mini-bar" aria-hidden="true">
                              <span
                                className="seg-mini-exp"
                                style={{ width: `${Math.min(100, (expected / Math.max(expected, actual, 1)) * 100)}%` }}
                              />
                            </span>
                            <span className="seg-tonnes">{actual.toFixed(0)}/{expected.toFixed(0)}</span>
                          </div>
                        )
                      })}
                    </div>
                  </td>
                  <td className="num">{f.exported_t.toFixed(1)} t</td>
                  <td className={`num ${f.local_t > 0 ? 'delta-below' : ''}`}>{f.local_t.toFixed(1)} t</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      {rows.length === 0 && <Empty label="No farm matches the filter." />}
    </Section>
  )
}
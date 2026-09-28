import type { KpiReport } from '../types'
import { MetricCard, money, tonnes } from './ui'

export function KpiBanner({ kpis }: { kpis: KpiReport }) {
  const exportShare = kpis.actual_received_t > 0 ? (kpis.export_t / kpis.actual_received_t) * 100 : 0
  const capacityShare = kpis.station_capacity_t > 0 ? (kpis.export_t / kpis.station_capacity_t) * 100 : 0
  return (
    <div className="kpi-grid" aria-label="Key decision metrics">
      <MetricCard
        label="Crop received"
        value={tonnes(kpis.actual_received_t)}
        sub={`vs ${kpis.expected_plan_t} t planned`}
        tone={kpis.actual_received_t < kpis.expected_plan_t ? 'warn' : 'good'}
        hint={`${((kpis.actual_received_t / kpis.expected_plan_t) * 100).toFixed(1)}% of plan`}
      />
      <MetricCard
        label="Exported"
        value={tonnes(kpis.export_t)}
        sub={`station capacity ${tonnes(kpis.station_capacity_t)}`}
        tone={capacityShare >= 100 ? 'brand' : 'neutral'}
        hint={`${capacityShare.toFixed(1)}% of station capacity used`}
      />
      <MetricCard
        label="Export rate"
        value={`${kpis.export_rate_pct}%`}
        tone="good"
        hint={`${exportShare.toFixed(1)}% of the crop kept`}
      />
      <MetricCard
        label="Local residual"
        value={tonnes(kpis.local_t)}
        sub={`value ${money(kpis.local_value_eur)}`}
        tone={kpis.local_t > 0 ? 'bad' : 'good'}
        hint="10% of reference segment price"
      />
      <MetricCard
        label="Export revenue"
        value={money(kpis.export_revenue_eur)}
        tone="good"
        hint="protected higher-price orders first"
      />
      <MetricCard
        label="Total value"
        value={money(kpis.total_value_eur)}
        sub={`${kpis.partial_client_count} partial · ${kpis.unserved_client_count} unserved`}
        tone="neutral"
        hint={`${kpis.at_risk_client_count} of ${kpis.complete_client_count + kpis.partial_client_count + kpis.unserved_client_count} clients at risk`}
      />
    </div>
  )
}
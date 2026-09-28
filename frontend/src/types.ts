// API response types — mirror the pydantic schemas on the server.

export interface DataHealth {
  expected_total_t: number
  actual_total_t: number
  actual_by_segment_t: Record<Segment, number>
  expected_by_segment_t: Record<Segment, number>
  station_capacity_t: number
  reference_prices: Record<Segment, number>
  farm_count: number
  client_count: number
  issues: string[]
}

export type Segment = 'A' | 'B' | 'C' | 'D'

export interface AllocationRow {
  farm_id: string
  farm_name: string
  segment: Segment
  client_id: string
  client_name: string
  tonnes: number
  quality_upgrade: number
  export_revenue_eur: number
}

export interface SegmentVariance {
  segment: Segment
  expected_t: number
  actual_t: number
  variance_t: number
}

export interface FarmComparison {
  farm_id: string
  farm_name: string
  expected_capacity_t: number
  actual_total_t: number
  capacity_variance_t: number
  segment_variances: SegmentVariance[]
  local_t: number
  exported_t: number
}

export type ClientStatusKind = 'COMPLETE' | 'PARTIAL' | 'UNSERVED'

export interface ClientStatus {
  client_id: string
  client_name: string
  acceptance_mode: string
  requested_segment: Segment
  demand_t: number
  allocated_t: number
  remaining_t: number
  export_revenue_eur: number
  status: ClientStatusKind
  shortage_reason: string | null
}

export interface LocalResidual {
  farm_id: string
  segment: Segment
  local_t: number
  local_value_eur: number
  reference_price_per_t_eur: number
}

export interface KpiReport {
  expected_plan_t: number
  actual_received_t: number
  station_capacity_t: number
  export_t: number
  export_rate: number
  export_rate_pct: number
  local_t: number
  export_revenue_eur: number
  local_value_eur: number
  total_value_eur: number
  at_risk_client_count: number
  complete_client_count: number
  partial_client_count: number
  unserved_client_count: number
}

export interface PlanResult {
  allocations: AllocationRow[]
  client_statuses: ClientStatus[]
  farm_comparisons: FarmComparison[]
  local_residuals: LocalResidual[]
  kpis: KpiReport
  data_health: DataHealth
}

export interface ValidationIssue {
  location: string
  message: string
}

export interface ApiError {
  error: string
  detail: string | null
  issues: ValidationIssue[]
}

export interface AssistantResponse {
  mode: 'deterministic' | 'llm'
  answer: string
  evidence: string[]
  configured: boolean
  question_type: string | null
  using_deterministic_fallback: boolean
}

export interface HealthResponse {
  status: string
  assistant_configured: boolean
}
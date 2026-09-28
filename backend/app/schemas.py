"""Typed result models for the API responses.

Every figure that leaves the server passes through one of these
models. They mirror the JSON contract consumed by the frontend.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Domain models (a validated copy of the workbook)
# ---------------------------------------------------------------------------


class FarmPlan(BaseModel):
    farm_id: str
    farm_name: str
    expected_daily_capacity_t: float
    expected_mix_pct: dict[str, float]  # segment -> fraction [0, 1]
    actual_t: dict[str, float]  # segment -> tonnes


class ClientOrder(BaseModel):
    client_id: str
    client_name: str
    acceptance_mode: str
    requested_segment: str
    demand_t: float
    export_price_per_t_eur: float


class StationConfig(BaseModel):
    station_id: str
    export_conditioning_capacity_t: float
    local_market_ratio: float
    reference_export_price_per_t_eur: dict[str, float]

class WorkbookData(BaseModel):
    farms: list[FarmPlan]
    clients: list[ClientOrder]
    station: StationConfig
    source_path: str | None = None



# ---------------------------------------------------------------------------
# Load / validation output
# ---------------------------------------------------------------------------

class FarmVariance(BaseModel):
    farm_id: str
    segment: str
    expected_t: float
    actual_t: float
    variance_t: float

class DataHealth(BaseModel):
    expected_total_t: float = Field(description="Sum of expected farm capacity")
    actual_total_t: float = Field(description="Sum of actual farm receipts")
    actual_by_segment_t: dict[str, float]
    expected_by_segment_t: dict[str, float]
    station_capacity_t: float
    reference_prices: dict[str, float]
    farm_count: int
    client_count: int
    issues: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Planning output
# ---------------------------------------------------------------------------


class AllocationRow(BaseModel):
    farm_id: str
    farm_name: str
    segment: str
    client_id: str
    client_name: str
    tonnes: float
    quality_upgrade: int = Field(description="0 = requested segment, >0 = better than requested")
    export_revenue_eur: float


class SegmentVariance(BaseModel):
    segment: str
    expected_t: float
    actual_t: float
    variance_t: float


class FarmComparison(BaseModel):
    farm_id: str
    farm_name: str
    expected_capacity_t: float
    actual_total_t: float
    capacity_variance_t: float
    segment_variances: list[SegmentVariance]
    local_t: float
    exported_t: float


class ClientStatus(BaseModel):
    client_id: str
    client_name: str
    acceptance_mode: str
    requested_segment: str
    demand_t: float
    allocated_t: float
    remaining_t: float
    export_revenue_eur: float
    status: str  # COMPLETE | PARTIAL | UNSERVED
    shortage_reason: str | None = None


class LocalResidual(BaseModel):
    farm_id: str
    segment: str
    local_t: float
    local_value_eur: float
    reference_price_per_t_eur: float


class KpiReport(BaseModel):
    expected_plan_t: float
    actual_received_t: float
    station_capacity_t: float
    export_t: float
    export_rate: float  # 0..1 raw ratio
    export_rate_pct: float  # rounded to one decimal
    local_t: float
    export_revenue_eur: float
    local_value_eur: float
    total_value_eur: float
    at_risk_client_count: int
    complete_client_count: int
    partial_client_count: int
    unserved_client_count: int


class PlanResult(BaseModel):
    allocations: list[AllocationRow]
    client_statuses: list[ClientStatus]
    farm_comparisons: list[FarmComparison]
    local_residuals: list[LocalResidual]
    variances: list[FarmVariance]
    kpis: KpiReport
    data_health: DataHealth


# ---------------------------------------------------------------------------
# Assistant
# ---------------------------------------------------------------------------


class AssistantRequest(BaseModel):
    question: str = Field(min_length=3, max_length=1000)


class AssistantResponse(BaseModel):
    mode: str = Field(description="deterministic | llm")
    answer: str
    evidence: list[str] = Field(default_factory=list, description="Resolvable IDs cited")
    configured: bool = Field(description="A live model path is configured")
    question_type: str | None = None
    using_deterministic_fallback: bool = False


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class ValidationIssue(BaseModel):
    location: str  # e.g. "Farms:F03"
    message: str


class ErrorResponse(BaseModel):
    error: str
    detail: str | None = None
    issues: list[ValidationIssue] = Field(default_factory=list)
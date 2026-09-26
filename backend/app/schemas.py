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
# Errors
# ---------------------------------------------------------------------------


class ValidationIssue(BaseModel):
    location: str  # e.g. "Farms:F03"
    message: str


class ErrorResponse(BaseModel):
    error: str
    detail: str | None = None
    issues: list[ValidationIssue] = Field(default_factory=list)
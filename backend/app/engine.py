"""Deterministic daily export planning policy.

Implements the authoritative reference policy exactly:
  1..3. Available supply comes from each farm's actual A/B/C/D tonnes
         (planned values are for comparison, never for allocation).
  4.    Client orders are processed by export price per tonne
         descending, ties broken by client_id.
  5.    For the current client, only compatible farm-segment supply
         with a positive balance is kept.
  6.    Compatible supply is sorted by the smallest quality upgrade,
         then farm_id — this creates the farm-to-client assignment.
  7.    Allocation advances in 5 t steps until client demand, supply
         or station capacity is exhausted.
  8.    Every unexported actual tonne goes to the local market; local
         value = residual × local ratio × segment reference price.
  9.    The same input always returns the same output.

Human-in-the-loop note: this computes a *proposal*. It never contacts
farms or clients and writes nothing to an external system.
"""

from __future__ import annotations

from .loader import build_data_health
from .schemas import (
    AllocationRow,
    ClientStatus,
    FarmComparison,
    FarmVariance,
    KpiReport,
    LocalResidual,
    PlanResult,
    SegmentVariance,
    WorkbookData,
)
from .segments import compatible_segments, upgrade_distance

STEP = 5.0


def _floor_to_step(value: float, step: float = STEP) -> float:
    import math

    steps = math.floor(value / step + 1e-9)
    return steps * step


def run_plan(data: WorkbookData) -> PlanResult:
    farms = {f.farm_id: f for f in data.farms}
    clients = data.clients
    station = data.station

    # 1. Available supply: farm-segment balances from actual receipts.
    balances: dict[tuple[str, str], float] = {}
    for farm in farms.values():
        for seg, tonnes in farm.actual_t.items():
            if tonnes > 0:
                balances[(farm.farm_id, seg)] = tonnes

    allocation_rows: list[AllocationRow] = []
    client_statuses: list[ClientStatus] = []
    used_capacity = 0.0

    # 2. Processing order: export price desc, then client_id.
    ordered = sorted(clients, key=lambda c: (c.export_price_per_t_eur, c.client_id), reverse=True)

    for client in ordered:
        demand = client.demand_t
        compat = _compatible_rows(balances, client)
        served = 0.0
        remaining_capacity = station.export_conditioning_capacity_t - used_capacity

        for (farm_id, seg) in compat:
            if served >= demand or remaining_capacity <= 0:
                break
            take = min(demand - served, balances[(farm_id, seg)], remaining_capacity)
            take = _floor_to_step(take)
            if take <= 0:
                continue

            balances[(farm_id, seg)] -= take
            used_capacity += take
            remaining_capacity -= take
            served += take
            allocation_rows.append(
                AllocationRow(
                    farm_id=farm_id,
                    farm_name=farms[farm_id].farm_name,
                    segment=seg,
                    client_id=client.client_id,
                    client_name=client.client_name,
                    tonnes=take,
                    quality_upgrade=upgrade_distance(client.requested_segment, seg),
                    export_revenue_eur=round(take * client.export_price_per_t_eur, 2),
                )
            )

        status = "COMPLETE" if served >= demand - 1e-9 else ("PARTIAL" if served > 0 else "UNSERVED")
        reason = None
        if status != "COMPLETE":
            if remaining_capacity <= 1e-9:
                reason = "STATION_CAPACITY_REACHED"
            else:
                reason = "INSUFFICIENT_COMPATIBLE_SEGMENT"
        client_statuses.append(
            ClientStatus(
                client_id=client.client_id,
                client_name=client.client_name,
                acceptance_mode=client.acceptance_mode,
                requested_segment=client.requested_segment,
                demand_t=demand,
                allocated_t=served,
                remaining_t=round(demand - served, 2),
                export_revenue_eur=round(served * client.export_price_per_t_eur, 2),
                status=status,
                shortage_reason=reason,
            )
        )

    # 3. Local fallback: every unexported actual tonne.
    local_residuals: list[LocalResidual] = []
    for (farm_id, seg), tonnes in sorted(balances.items()):
        if tonnes <= 0:
            continue
        ref = station.reference_export_price_per_t_eur[seg]
        local_residuals.append(
            LocalResidual(
                farm_id=farm_id,
                segment=seg,
                local_t=round(tonnes, 2),
                local_value_eur=round(tonnes * station.local_market_ratio * ref, 2),
                reference_price_per_t_eur=ref,
            )
        )

    # Farm-vs-plan comparison and residual local tonnes per farm.
    exported_by_farm_segment: dict[tuple[str, str], float] = {}
    for row in allocation_rows:
        key = (row.farm_id, row.segment)
        exported_by_farm_segment[key] = exported_by_farm_segment.get(key, 0.0) + row.tonnes

    farm_comparisons: list[FarmComparison] = []
    variances: list[FarmVariance] = []
    local_by_farm = {f.farm_id: 0.0 for f in data.farms}
    local_by_farm_seg: dict[tuple[str, str], float] = {}
    for res in local_residuals:
        local_by_farm[res.farm_id] += res.local_t
        local_by_farm_seg[(res.farm_id, res.segment)] = res.local_t

    for farm in data.farms:
        seg_vars = []
        actual_total = sum(farm.actual_t.values())
        for seg in ["A", "B", "C", "D"]:
            expected = farm.expected_daily_capacity_t * farm.expected_mix_pct[seg]
            actual = farm.actual_t[seg]
            seg_vars.append(
                SegmentVariance(
                    segment=seg,
                    expected_t=round(expected, 2),
                    actual_t=round(actual, 2),
                    variance_t=round(actual - expected, 2),
                )
            )
            variances.append(
                FarmVariance(
                    farm_id=farm.farm_id,
                    segment=seg,
                    expected_t=round(expected, 2),
                    actual_t=round(actual, 2),
                    variance_t=round(actual - expected, 2),
                )
            )
        farm_comparisons.append(
            FarmComparison(
                farm_id=farm.farm_id,
                farm_name=farm.farm_name,
                expected_capacity_t=farm.expected_daily_capacity_t,
                actual_total_t=round(actual_total, 2),
                capacity_variance_t=round(actual_total - farm.expected_daily_capacity_t, 2),
                segment_variances=seg_vars,
                local_t=round(local_by_farm[farm.farm_id], 2),
                exported_t=round(actual_total - local_by_farm[farm.farm_id], 2),
            )
        )

    # 4. KPIs.
    actual_received = sum(res.local_t for res in local_residuals) + used_capacity
    export_revenue = sum(r.export_revenue_eur for r in allocation_rows)
    local_value = sum(r.local_value_eur for r in local_residuals)
    total_value = export_revenue + local_value
    export_rate = used_capacity / actual_received if actual_received else 0.0

    at_risk = [c for c in client_statuses if c.status != "COMPLETE"]
    kpis = KpiReport(
        expected_plan_t=round(sum(f.expected_daily_capacity_t for f in data.farms), 2),
        actual_received_t=round(actual_received, 2),
        station_capacity_t=station.export_conditioning_capacity_t,
        export_t=used_capacity,
        export_rate=round(export_rate, 6),
        export_rate_pct=round(export_rate * 100, 1),
        local_t=round(actual_received - used_capacity, 2),
        export_revenue_eur=round(export_revenue, 2),
        local_value_eur=round(local_value, 2),
        total_value_eur=round(total_value, 2),
        at_risk_client_count=len(at_risk),
        complete_client_count=sum(1 for c in client_statuses if c.status == "COMPLETE"),
        partial_client_count=sum(1 for c in client_statuses if c.status == "PARTIAL"),
        unserved_client_count=sum(1 for c in client_statuses if c.status == "UNSERVED"),
    )

    return PlanResult(
        allocations=allocation_rows,
        client_statuses=client_statuses,
        farm_comparisons=farm_comparisons,
        local_residuals=local_residuals,
        variances=variances,
        kpis=kpis,
        data_health=build_data_health(data),
    )


def _compatible_rows(balances, client) -> list[tuple[str, str]]:
    """Compatible farm-segment rows, smallest upgrade first, then farm_id.

    'Smallest quality upgrade' follows the brief: for a MINIMUM C client,
    C is preferred before B or A. A supply segment exactly matching the
    requested one has upgrade 0; a better one has a positive upgrade.
    """
    accepted = compatible_segments(client.acceptance_mode, client.requested_segment)
    rows = []
    for (farm_id, seg), tonnes in balances.items():
        if seg not in accepted or tonnes <= 0:
            continue
        rows.append(
            (
                upgrade_distance(client.requested_segment, seg),  # upgrade
                farm_id,
                seg,
            )
        )
    rows.sort()
    return [(farm_id, seg) for (_, farm_id, seg) in rows]
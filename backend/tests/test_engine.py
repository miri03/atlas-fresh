"""Planning-policy tests: baseline parity, ordering, compatibility, hard
limits, local residual, reasons and determinism."""

from __future__ import annotations

from app.engine import run_plan
from app.schemas import WorkbookData
from app.segments import compatible_segments, upgrade_distance

from .conftest import make_client, make_farm, make_station


def test_baseline_matches_public_checks(workbook):
    result = run_plan(workbook)
    k = result.kpis
    assert k.expected_plan_t == 600.0
    assert k.actual_received_t == 560.0
    assert k.station_capacity_t == 500.0
    assert k.export_t == 500.0
    assert k.export_rate_pct == 89.3
    assert k.local_t == 60.0
    assert k.export_revenue_eur == 549_500.0
    assert k.local_value_eur == 4_500.0
    assert k.total_value_eur == 554_000.0
    assert k.at_risk_client_count == 3

    assert result.data_health.actual_by_segment_t == {"A": 90.0, "B": 160.0, "C": 180.0, "D": 130.0}


def test_baseline_client_statuses_and_reasons(workbook):
    statuses = {c.client_id: c for c in run_plan(workbook).client_statuses}
    assert statuses["C01"].status == "COMPLETE"
    assert statuses["C02"].status == "PARTIAL"
    assert statuses["C02"].shortage_reason == "INSUFFICIENT_COMPATIBLE_SEGMENT"
    assert statuses["C03"].status == "COMPLETE"
    assert statuses["C09"].status == "PARTIAL"
    assert statuses["C09"].shortage_reason == "INSUFFICIENT_COMPATIBLE_SEGMENT"
    assert statuses["C08"].status == "PARTIAL"
    assert statuses["C08"].shortage_reason == "STATION_CAPACITY_REACHED"


def test_invariants_hold(workbook):
    result = run_plan(workbook)
    station_cap = workbook.station.export_conditioning_capacity_t
    assert sum(a.tonnes for a in result.allocations) <= station_cap
    for a in result.allocations:
        assert a.tonnes <= workbook.station.export_conditioning_capacity_t
    for c in result.client_statuses:
        assert c.allocated_t <= c.demand_t
    assert sum(c.allocated_t for c in result.client_statuses) == result.kpis.export_t

    by_farm_seg: dict[tuple[str, str], float] = {}
    for a in result.allocations:
        by_farm_seg[(a.farm_id, a.segment)] = by_farm_seg.get((a.farm_id, a.segment), 0.0) + a.tonnes
    for f in workbook.farms:
        for seg, tonnes in f.actual_t.items():
            assert by_farm_seg.get((f.farm_id, seg), 0.0) <= tonnes

    exported = sum(a.tonnes for a in result.allocations)
    local = sum(r.local_t for r in result.local_residuals)
    assert abs((exported + local) - result.kpis.actual_received_t) < 1e-9


def test_all_allocations_are_compatible(workbook):
    result = run_plan(workbook)
    for a in result.allocations:
        client = next(c for c in workbook.clients if c.client_id == a.client_id)
        accepted = compatible_segments(client.acceptance_mode, client.requested_segment)
        assert a.segment in accepted
        assert upgrade_distance(client.requested_segment, a.segment) >= 0


def test_higher_price_client_served_first():
    data = WorkbookData(
        farms=[
            make_farm("F01", 30, {"A": 1.0, "B": 0, "C": 0, "D": 0}, {"A": 15, "B": 0, "C": 0, "D": 0}),
        ],
        clients=[
            make_client("C12", "EXACT", "A", 15, 1000),
            make_client("C11", "EXACT", "A", 15, 1500),
        ],
        station=make_station(),
    )
    result = run_plan(data)
    statuses = {c.client_id: c for c in result.client_statuses}
    assert statuses["C11"].status == "COMPLETE"
    assert statuses["C11"].allocated_t == 15
    assert statuses["C12"].status == "UNSERVED"


def test_minimum_client_prefers_exact_segment():
    # C has 10t, B has 20t; a MINIMUM C client demanding 15t should take C first.
    data = WorkbookData(
        farms=[
            make_farm("F01", 30, {"A": 0, "B": 0.5, "C": 0.5, "D": 0}, {"A": 0, "B": 20, "C": 10, "D": 0}),
        ],
        clients=[make_client("C01", "MINIMUM", "C", 15, 1000)],
        station=make_station(),
    )
    allocations = run_plan(data).allocations
    c_rows = [(a.segment, a.tonnes) for a in allocations if a.segment == "C"]
    assert c_rows == [("C", 10)]
    assert allocations[0].quality_upgrade == 0
    # The remaining 5 t comes from B (a one-level upgrade).
    assert sum(a.tonnes for a in allocations) == 15


def test_exact_client_never_receives_better_segment():
    data = WorkbookData(
        farms=[
            make_farm("F01", 30, {"A": 0.5, "B": 0.5, "C": 0, "D": 0}, {"A": 20, "B": 10, "C": 0, "D": 0}),
        ],
        clients=[make_client("C01", "EXACT", "B", 15, 1000)],
        station=make_station(),
    )
    result = run_plan(data)
    assert all(a.segment == "B" for a in result.allocations)


def test_station_capacity_is_a_hard_limit():
    data = WorkbookData(
        farms=[
            make_farm("F01", 30, {"A": 1.0, "B": 0, "C": 0, "D": 0}, {"A": 30, "B": 0, "C": 0, "D": 0}),
        ],
        clients=[make_client("C01", "EXACT", "A", 50, 1000)],
        station=make_station(capacity=10),
    )
    result = run_plan(data)
    assert result.kpis.export_t == 10
    client = result.client_statuses[0]
    assert client.status == "PARTIAL"
    assert client.shortage_reason == "STATION_CAPACITY_REACHED"
    assert result.kpis.local_t == 20


def test_segment_shortage_reason():
    data = WorkbookData(
        farms=[
            make_farm("F01", 30, {"A": 1.0, "B": 0, "C": 0, "D": 0}, {"A": 10, "B": 0, "C": 0, "D": 0}),
        ],
        clients=[make_client("C01", "EXACT", "A", 50, 1000)],
        station=make_station(capacity=500),
    )
    result = run_plan(data)
    client = result.client_statuses[0]
    assert client.status == "PARTIAL"
    assert client.shortage_reason == "INSUFFICIENT_COMPATIBLE_SEGMENT"


def test_local_value_formula():
    # 10t of D goes local; D ref price 750, ratio 0.1 -> 10*0.1*750 = 750.
    data = WorkbookData(
        farms=[
            make_farm("F01", 10, {"A": 0, "B": 0, "C": 0, "D": 1.0}, {"A": 0, "B": 0, "C": 0, "D": 10}),
        ],
        clients=[make_client("C01", "MINIMUM", "A", 5, 9000)],
        station=make_station(capacity=500, ratio=0.1),
    )
    result = run_plan(data)
    res = result.local_residuals[0]
    assert res.local_t == 10
    assert res.local_value_eur == 750
    assert result.kpis.local_value_eur == 750


def test_plan_is_deterministic(workbook):
    a = run_plan(workbook)
    b = run_plan(workbook)
    assert [a.model_dump() for a in a.allocations] == [a.model_dump() for a in b.allocations]
    assert [c.model_dump() for c in a.client_statuses] == [c.model_dump() for c in b.client_statuses]


def test_output_changes_when_valid_input_changes(workbook):
    base = run_plan(workbook)
    mutated = workbook.model_copy(deep=True)
    mutated.clients[0].demand_t = 25  # valid: still a multiple of 5
    altered = run_plan(mutated)
    assert altered.client_statuses[0].allocated_t == 25
    assert [a.model_dump() for a in altered.allocations] != [a.model_dump() for a in base.allocations]


def test_variances_match_segment_formula():
    data = WorkbookData(
        farms=[
            make_farm("F01", 40, {"A": 0.5, "B": 0.5, "C": 0, "D": 0}, {"A": 15, "B": 25, "C": 0, "D": 0}),
        ],
        clients=[make_client("C01", "MINIMUM", "A", 20, 1000)],
        station=make_station(),
    )
    result = run_plan(data)
    f = result.farm_comparisons[0]
    a = next(s for s in f.segment_variances if s.segment == "A")
    assert a.expected_t == 20
    assert a.actual_t == 15
    assert a.variance_t == -5


def test_minimum_d_prefers_d_over_c_over_b_over_a():
    data = WorkbookData(
        farms=[
            make_farm("F01", 40, {"A": 0.25, "B": 0.25, "C": 0.25, "D": 0.25}, {"A": 10, "B": 10, "C": 10, "D": 10}),
        ],
        clients=[make_client("C01", "MINIMUM", "D", 30, 1000)],
        station=make_station(),
    )
    alloc = run_plan(data).allocations
    assert [a.segment for a in alloc] == ["D", "C", "B"]  # exact first, then better ones
    assert [a.quality_upgrade for a in alloc] == [0, 1, 2]
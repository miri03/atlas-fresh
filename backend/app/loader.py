"""Read the Atlas Fresh workbook and validate it against the business rules.

Validation is strict and never repairs data silently. Every issue carries
the sheet and the farm/client ID it concerns, so a user can act on it.

The supplied workbook is left untouched: we only read it. Computed results
never share a file with source data.
"""

from __future__ import annotations

from pathlib import Path

import openpyxl

from .schemas import FarmPlan, ClientOrder, StationConfig, WorkbookData

FIVE_TOL = 1e-9
MIX_TOL = 1e-6
REQUIRED_REFERENCE_SEGMENTS = ["A", "B", "C", "D"]

# Column names as they appear in each sheet header row.
FARM_HEADER = ("farm_id",)
CLIENT_HEADER = ("client_id",)
STATION_HEADER = ("station_id",)
PRICE_HEADER = ("segment",)


class WorkbookValidationError(Exception):
    """Raised when the workbook violates a business rule."""

    def __init__(self, issues: list[tuple[str, str]]):
        self.issues = issues  # list of (location, message)


def _is_empty(row: tuple) -> bool:
    return all(v is None or str(v).strip() == "" for v in row)


def _find_header_row(ws, marker_col: int, marker_value: str) -> int | None:
    for i, row in enumerate(ws.iter_rows(values_only=True), start=1):
        if row and marker_col <= len(row) and row[marker_col - 1] == marker_value:
            return i
    return None


def _is_multiple_of_5(value: float) -> bool:
    return abs(round(value / 5.0) * 5.0 - value) <= FIVE_TOL


def _key(ws_title: str, v: str) -> str:
    return f"{ws_title}:{v}"


def _validate_farms(ws) -> tuple[list[FarmPlan], list[tuple[str, str]]]:
    issues: list[tuple[str, str]] = []
    header = _find_header_row(ws, 1, "farm_id")
    if header is None:
        raise WorkbookValidationError([("Farms", "header row with 'farm_id' not found")])

    plan_data = []
    seen: set[str] = set()
    for row in ws.iter_rows(min_row=header + 1, values_only=True):
        if _is_empty(row):
            continue
        farm_id = str(row[0]).strip()
        if not farm_id:
            continue
        loc = _key("Farms", farm_id)
        if farm_id in seen:
            issues.append((loc, f"duplicate farm_id '{farm_id}'"))
            continue
        seen.add(farm_id)

        try:
            expected_capacity = float(row[2])
        except (TypeError, ValueError):
            issues.append((loc, "expected_daily_capacity_t is not a number"))
            continue
        if expected_capacity < 0:
            issues.append((loc, "expected_daily_capacity_t must be non-negative"))

        mix = {}
        for col_idx, seg in zip(range(3, 7), ["A", "B", "C", "D"]):
            try:
                val = float(row[col_idx])
            except (TypeError, ValueError):
                issues.append((loc, f"expected_{seg}_pct is not a number"))
                continue
            mix[seg] = val
            if val < 0 or val > 1:
                issues.append((loc, f"expected_{seg}_pct={val} outside [0,1]"))

        mix_sum = sum(mix.values())
        if abs(mix_sum - 1.0) > MIX_TOL:
            issues.append((loc, f"expected mix sums to {mix_sum:.4f}, must sum to 1.0"))

        actual = {}
        for col_idx, seg in zip(range(7, 11), ["A", "B", "C", "D"]):
            try:
                val = float(row[col_idx])
            except (TypeError, ValueError):
                issues.append((loc, f"actual_{seg}_t is not a number"))
                continue
            actual[seg] = val
            if val < 0:
                issues.append((loc, f"actual_{seg}_t must be non-negative"))
            elif not _is_multiple_of_5(val):
                issues.append((loc, f"actual_{seg}_t={val} is not a multiple of 5 t"))

        plan_data.append(
            FarmPlan(
                farm_id=farm_id,
                farm_name=str(row[1]).strip() if row[1] else farm_id,
                expected_daily_capacity_t=expected_capacity,
                expected_mix_pct=mix,
                actual_t=actual,
            )
        )
    if not plan_data:
        issues.append(("Farms", "no farm rows found"))
    return plan_data, issues


def _validate_clients(ws) -> tuple[list[ClientOrder], list[tuple[str, str]]]:
    issues: list[tuple[str, str]] = []
    header = _find_header_row(ws, 1, "client_id")
    if header is None:
        raise WorkbookValidationError([("Clients", "header row with 'client_id' not found")])

    orders, seen = [], set()
    for row in ws.iter_rows(min_row=header + 1, values_only=True):
        if _is_empty(row):
            continue
        client_id = str(row[0]).strip()
        if not client_id:
            continue
        loc = _key("Clients", client_id)
        if client_id in seen:
            issues.append((loc, f"duplicate client_id '{client_id}'"))
            continue
        seen.add(client_id)

        mode = str(row[2]).strip().upper() if row[2] else ""
        segment = str(row[3]).strip().upper() if row[3] else ""
        if mode not in ("EXACT", "MINIMUM"):
            issues.append((loc, f"acceptance_mode '{mode}' is invalid, expected EXACT or MINIMUM"))
        if segment not in ("A", "B", "C", "D"):
            issues.append((loc, f"requested_segment '{segment}' is invalid, expected A/B/C/D"))

        try:
            demand = float(row[4])
        except (TypeError, ValueError):
            issues.append((loc, "demand_t is not a number"))
            continue
        if demand < 0:
            issues.append((loc, "demand_t must be non-negative"))
        elif not _is_multiple_of_5(demand):
            issues.append((loc, f"demand_t={demand} is not a multiple of 5 t"))

        try:
            price = float(row[5])
        except (TypeError, ValueError):
            issues.append((loc, "export_price_per_t_eur is not a number"))
            continue
        if price < 0:
            issues.append((loc, "export_price_per_t_eur must be non-negative"))

        orders.append(
            ClientOrder(
                client_id=client_id,
                client_name=str(row[1]).strip() if row[1] else client_id,
                acceptance_mode=mode,
                requested_segment=segment,
                demand_t=demand,
                export_price_per_t_eur=price,
            )
        )
    if not orders:
        issues.append(("Clients", "no client rows found"))
    return orders, issues


def _validate_station(ws) -> tuple[StationConfig, list[tuple[str, str]]]:
    issues: list[tuple[str, str]] = []
    header = _find_header_row(ws, 1, "station_id")
    if header is None:
        raise WorkbookValidationError([("Station", "header row with 'station_id' not found")])

    station_row = None
    for row in ws.iter_rows(min_row=header + 1, values_only=True):
        if _is_empty(row):
            continue
        if str(row[0]).strip().upper().startswith("STATION"):
            station_row = row
            break
    if station_row is None:
        raise WorkbookValidationError([("Station", "no station row found")])

    station_id = str(station_row[0]).strip()
    loc = _key("Station", station_id)

    try:
        capacity = float(station_row[1])
    except (TypeError, ValueError):
        issues.append((loc, "export_conditioning_capacity_t is not a number"))
        capacity = 0.0
    if capacity <= 0:
        issues.append((loc, "capacity must be positive"))
    elif not _is_multiple_of_5(capacity):
        issues.append((loc, f"export_conditioning_capacity_t={capacity} is not a multiple of 5 t"))

    try:
        ratio = float(station_row[2])
    except (TypeError, ValueError):
        issues.append((loc, "local_market_ratio is not a number"))
        ratio = 0.0
    if ratio < 0 or ratio > 1:
        issues.append((loc, f"local_market_ratio={ratio} outside [0,1]"))

    # Reference export prices by segment (must be complete).
    price_header = _find_header_row(ws, 1, "segment")
    ref_prices: dict[str, float] = {}
    if price_header is not None:
        for row in ws.iter_rows(min_row=price_header + 1, values_only=True):
            if _is_empty(row):
                continue
            seg = str(row[0]).strip().upper()
            if seg in ("A", "B", "C", "D"):
                try:
                    ref_prices[seg] = float(row[1])
                except (TypeError, ValueError):
                    issues.append((_key("Station", seg), "reference_export_price is not a number"))
    for seg in REQUIRED_REFERENCE_SEGMENTS:
        if seg not in ref_prices:
            issues.append(("Station", f"missing reference export price for segment {seg}"))
        elif ref_prices[seg] < 0:
            issues.append((_key("Station", seg), "reference export price must be non-negative"))

    return station_id, capacity, ratio, ref_prices, issues


def load_workbook(path: str | Path) -> WorkbookData:
    """Parse and validate the workbook. Raises WorkbookValidationError."""
    path = Path(path)
    if not path.exists():
        raise WorkbookValidationError([("Farms", f"file not found: {path}")])

    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    try:
        if "Farms" not in wb.sheetnames:
            raise WorkbookValidationError([("Farms", "sheet 'Farms' missing from workbook")])
        if "Clients" not in wb.sheetnames:
            raise WorkbookValidationError([("Clients", "sheet 'Clients' missing from workbook")])
        if "Station" not in wb.sheetnames:
            raise WorkbookValidationError([("Station", "sheet 'Station' missing from workbook")])

        issues: list[tuple[str, str]] = []
        farms, farm_issues = _validate_farms(wb["Farms"])
        clients, client_issues = _validate_clients(wb["Clients"])
        station_id, capacity, ratio, ref_prices, station_issues = _validate_station(wb["Station"])
        issues += farm_issues + client_issues + station_issues

        if issues:
            raise WorkbookValidationError(issues)

        return WorkbookData(
            farms=farms,
            clients=clients,
            station=StationConfig(
                station_id=station_id,
                export_conditioning_capacity_t=capacity,
                local_market_ratio=ratio,
                reference_export_price_per_t_eur=ref_prices,
            ),
            source_path=str(path),
        )
    finally:
        wb.close()


def build_data_health(data: WorkbookData) -> dict:
    """Compact health summary shown at the top of the workspace."""
    expected_total = sum(f.expected_daily_capacity_t for f in data.farms)
    actual_by_segment = {s: 0.0 for s in ["A", "B", "C", "D"]}
    expected_by_segment = {s: 0.0 for s in ["A", "B", "C", "D"]}
    for farm in data.farms:
        for seg in ["A", "B", "C", "D"]:
            actual_by_segment[seg] += farm.actual_t[seg]
            expected_by_segment[seg] += farm.expected_daily_capacity_t * farm.expected_mix_pct[seg]
    actual_total = sum(actual_by_segment.values())
    return {
        "expected_total_t": round(expected_total, 2),
        "actual_total_t": round(actual_total, 2),
        "actual_by_segment_t": {s: round(v, 2) for s, v in actual_by_segment.items()},
        "expected_by_segment_t": {s: round(v, 2) for s, v in expected_by_segment.items()},
        "station_capacity_t": data.station.export_conditioning_capacity_t,
        "reference_prices": data.station.reference_export_price_per_t_eur,
        "farm_count": len(data.farms),
        "client_count": len(data.clients),
        "issues": [],
    }
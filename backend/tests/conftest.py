"""Shared fixtures for the planning policy, validation and API tests."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from app.loader import load_workbook
from app.schemas import ClientOrder, FarmPlan, StationConfig, WorkbookData

DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "Atlas_Fresh_Production_Commercial_Data.xlsx"
ASSESSMENT_PATH = (
    Path(__file__).resolve().parents[2] / "Assessment_Pack" / "Atlas_Fresh_Production_Commercial_Data.xlsx"
)


@pytest.fixture(scope="session")
def workbook_path() -> Path:
    if not DATA_PATH.exists() and ASSESSMENT_PATH.exists():
        DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ASSESSMENT_PATH, DATA_PATH)
    assert DATA_PATH.exists(), f"workbook not found at {DATA_PATH}"
    return DATA_PATH


@pytest.fixture(scope="session")
def workbook(workbook_path) -> WorkbookData:
    return load_workbook(workbook_path)


def make_farm(fid: str, capacity: float, mix: dict[str, float], actual: dict[str, float]) -> FarmPlan:
    return FarmPlan(
        farm_id=fid,
        farm_name=f"Farm {fid}",
        expected_daily_capacity_t=capacity,
        expected_mix_pct=mix,
        actual_t=actual,
    )


def make_client(cid: str, mode: str, seg: str, demand: float, price: float) -> ClientOrder:
    return ClientOrder(
        client_id=cid,
        client_name=f"Client {cid}",
        acceptance_mode=mode,
        requested_segment=seg,
        demand_t=demand,
        export_price_per_t_eur=price,
    )


def make_station(capacity: float = 500, ratio: float = 0.1) -> StationConfig:
    return StationConfig(
        station_id="STATION-01",
        export_conditioning_capacity_t=capacity,
        local_market_ratio=ratio,
        reference_export_price_per_t_eur={"A": 1500, "B": 1250, "C": 1000, "D": 750},
    )
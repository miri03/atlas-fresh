"""API tests: seed/plan endpoints, validation mapping and SPA serving."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("ATLAS_DATA_PATH", str(Path(__file__).resolve().parents[2] / "data" / "Atlas_Fresh_Production_Commercial_Data.xlsx"))

from app.main import app  # noqa: E402

client = TestClient(app)


def test_health():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_seed_returns_health():
    resp = client.post("/api/seed")
    assert resp.status_code == 200
    body = resp.json()
    assert body["actual_total_t"] == 560.0
    assert body["expected_total_t"] == 600.0
    assert body["station_capacity_t"] == 500.0
    assert body["actual_by_segment_t"] == {"A": 90.0, "B": 160.0, "C": 180.0, "D": 130.0}

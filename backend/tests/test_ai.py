"""Grounded-assistant tests: evidence IDs, honest fallbacks, boundaries."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("ATLAS_DATA_PATH", str(Path(__file__).resolve().parents[2] / "data" / "Atlas_Fresh_Production_Commercial_Data.xlsx"))

from app import ai  # noqa: E402
from app.engine import run_plan  # noqa: E402
from app.loader import load_workbook  # noqa: E402


@pytest.fixture(scope="module")
def plan():
    data = load_workbook(os.environ["ATLAS_DATA_PATH"])
    return run_plan(data)


def test_classification(plan):
    assert ai.classify_question("Which clients are at risk and why?") == "at_risk"
    assert ai.classify_question("What are the biggest farm variances?") == "farm_gaps"
    assert ai.classify_question("Why are 60 t going local and what is their estimated value?") == "local_market"


def test_no_key_returns_deterministic_summary(plan, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    resp = ai.run_assistant(plan, "Which clients are at risk and why?")
    assert resp.mode == "deterministic"
    assert resp.configured is False
    assert resp.using_deterministic_fallback is True
    assert "C02" in resp.answer and "C08" in resp.answer and "C09" in resp.answer
    for e in resp.evidence:
        assert e in {"C02", "C08", "C09"}


def test_grounded_answer_cites_real_ids(plan):
    plan_result = plan
    resp = ai.run_assistant(plan_result, "Why are 60 t going local and what is their estimated value?")
    assert "60" in resp.answer
    assert resp.evidence, "expected segment evidence"
    known = {f.farm_id for f in plan_result.farm_comparisons} | {c.client_id for c in plan_result.client_statuses} | {"A", "B", "C", "D"}
    evidence = set(resp.evidence)
    assert evidence
    for e in evidence:
        assert e in known


def test_unsupported_question_is_honest(plan, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    resp = ai.run_assistant(plan, "What should I cook for dinner?")
    assert resp.using_deterministic_fallback
    assert "not covered" in resp.answer.lower()
    assert resp.evidence == []


def test_unknown_cited_ids_rejected(plan):
    allowed = {f.farm_id for f in plan.farm_comparisons} | {c.client_id for c in plan.client_statuses} | {"A", "B", "C", "D"}
    unknown = _cited_ids("F99 and A") - allowed
    assert unknown == {"F99"}
    assert ai.validate_llm_answer("F99 helped.", allowed) is not None
    assert ai.validate_llm_answer("A helped.", allowed) is None
    assert ai.validate_llm_answer("   ", allowed) is not None
    assert ai.validate_llm_answer("C02 served 40 t of A.", allowed) is None


def _cited_ids(text):
    return ai._cited_ids(text)


def test_provider_failure_falls_back_honestly(plan, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    def fake_ask(plan, question):
        return "", "provider HTTP 401"

    monkeypatch.setattr(ai, "ask_llm", fake_ask)
    resp = ai.run_assistant(plan, "Which clients are at risk and why?")
    assert resp.using_deterministic_fallback is True
    assert "provider HTTP 401" in resp.answer
    assert "C02" in resp.answer  # deterministic facts still present


def test_llm_answer_with_unknown_ids_is_honest(plan, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    # Simulate the real ask_llm path: its validation layer rejects output
    # that cites IDs not present in the plan and reports an error reason.
    def fake_ask(plan, question):
        return "", "model cited unknown IDs: C99"

    monkeypatch.setattr(ai, "ask_llm", fake_ask)
    resp = ai.run_assistant(plan, "Which clients are at risk and why?")
    assert resp.using_deterministic_fallback is True
    assert "model cited unknown IDs" in resp.answer
    # Deterministic facts are untouched and evidence stays resolvable.
    assert "C02" in resp.answer
    assert "C99" not in resp.evidence
    allowed = {f.farm_id for f in plan.farm_comparisons} | {c.client_id for c in plan.client_statuses}
    assert all(e in allowed for e in resp.evidence)
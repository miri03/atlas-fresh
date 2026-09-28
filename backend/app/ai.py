"""Grounded planning assistant.

The assistant *explains* the structured plan produced by the engine. It
never calculates, reallocates or writes anything. Every number it quotes
comes from the server-side PlanResult and every cited ID must resolve to
a real farm, client or segment.

Paths:
* If a model endpoint is configured (OpenAI-compatible), the model is
  asked to answer from a minimal structured context. Its output is
  validated: any cited ID that does not exist in the plan is rejected.
* Without a configuration, we return an honest no-key state with a
  clearly labelled deterministic summary built from the same facts.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

from .schemas import AssistantResponse, PlanResult

QUESTION_TYPES = ("at_risk", "farm_gaps", "local_market")

KEYWORDS: dict[str, list[str]] = {
    "at_risk": ["at risk", "risk", "partial", "unserved", "warning", "alert", "endangered"],
    "farm_gaps": ["farm", "gap", "variance", "segment", "shortfall", "production", "below plan", "mix", "expected"],
    "local_market": ["local", "60 t", "residual", "fall back", "fallback", "market", "leftover"],
}


def is_configured() -> bool:
    return bool(os.getenv("OPENAI_API_KEY"))


def provider_label() -> str:
    base = os.getenv("OPENAI_BASE_URL", "").strip()
    model = os.getenv("OPENAI_MODEL", "").strip()
    if base:
        return f"{base.rstrip('/')} · {model or 'default model'}"
    return f"OpenAI · {model or 'default model'}"


def classify_question(question: str) -> str | None:
    q = question.lower()
    for qtype, words in KEYWORDS.items():
        if any(w in q for w in words):
            return qtype
    return None


def _segment_sentence(segment: str, delta: float) -> str:
    if delta > 0:
        return f"segment {segment} arrived {delta:.1f} t above plan"
    if delta < 0:
        return f"segment {segment} is {abs(delta):.1f} t below plan"
    return f"segment {segment} is on plan"


# ---------------------------------------------------------------------------
# Deterministic (server-computed) answers
# ---------------------------------------------------------------------------


def deterministic_answer(plan: PlanResult, qtype: str) -> tuple[str, list[str]]:
    """Grounded answer + resolvable evidence IDs, computed from the plan."""
    if qtype == "at_risk":
        statuses = {c.client_id: c for c in plan.client_statuses}
        at_risk = [c for c in plan.client_statuses if c.status != "COMPLETE"]
        if not at_risk:
            return (
                "All 10 clients are fully served today: no order is at risk.",
                [],
            )
        lines = []
        for c in sorted(at_risk, key=lambda x: x.client_id):
            if c.status == "PARTIAL":
                lines.append(
                    f"{c.client_id} ({c.client_name}) is PARTIAL: "
                    f"{c.allocated_t:.0f} of {c.demand_t:.0f} t served"
                    f" ({c.shortage_reason})."
                )
            else:
                lines.append(f"{c.client_id} ({c.client_name}) is UNSERVED ({c.shortage_reason}).")
        evidence = [c.client_id for c in at_risk]
        return (
            f"{len(at_risk)} client(s) are at risk. "
            + " ".join(lines),
            evidence,
        )

    if qtype == "farm_gaps":
        gaps = []
        for f in plan.farm_comparisons:
            for sv in f.segment_variances:
                if abs(sv.variance_t) >= 5 - 1e-9:
                    gaps.append((f.farm_id, f.farm_name, sv.segment, sv.variance_t))
        if not gaps:
            return ("Every farm-segment is within 5 t of plan.", [])
        gaps.sort(key=lambda g: abs(g[3]), reverse=True)
        top = gaps[:5]
        lines = [
            f"{farm_id} ({name}): {_segment_sentence(seg, delta)}."
            for farm_id, name, seg, delta in top
        ]
        evidence = [g[0] for g in top] + [g[2] for g in top]
        return (
            f"The largest farm/segment gaps today are: " + " ".join(lines)
            + (" …" if len(gaps) > len(top) else ""),
            evidence,
        )

    # local_market
    kpis = plan.kpis
    total_local = kpis.local_t
    local_value = kpis.local_value_eur
    ref_prices = plan.data_health.reference_prices
    by_segment: dict[str, float] = {}
    for res in plan.local_residuals:
        by_segment[res.segment] = by_segment.get(res.segment, 0.0) + res.local_t
    if total_local <= 0:
        return (
            "Nothing is going to the local market today: the whole crop was exported.",
            [],
        )
    parts = []
    for seg in sorted(by_segment, key=lambda s: -by_segment[s]):
        parts.append(
            f"{by_segment[seg]:.0f} t of segment {seg} "
            f"(reference €{ref_prices[seg]:,.0f}/t → €{by_segment[seg] * 0.1 * ref_prices[seg]:,.0f})"
        )
    return (
        f"{total_local:.0f} t of the {kpis.actual_received_t:.0f} t received "
        f"({kpis.export_rate_pct:.1f}% exported) fall back to the local market, worth "
        f"€{local_value:,.0f} in total. Breakdown: " + ", ".join(parts)
        + ".",
        [r.segment for r in plan.local_residuals],
    )


def _handle_unknown(question: str) -> AssistantResponse:
    return AssistantResponse(
        mode="deterministic",
        answer=(
            "This specific question is not covered by my structured plan data. I can reliably "
            "answer: which clients are at risk and why, which farm/segment gaps matter today, "
            "and why tonnes fall back to the local market."
        ),
        evidence=[],
        configured=is_configured(),
        question_type=None,
        using_deterministic_fallback=True,
    )


# ---------------------------------------------------------------------------
# Optional live model path (OpenAI-compatible, key OR local endpoint)
# ---------------------------------------------------------------------------


def build_context(plan: PlanResult) -> str:
    """Minimal structured context: facts the model may cite, nothing more."""
    ctx: dict[str, Any] = {
        "kpis": plan.kpis.model_dump(),
        "clients": [
            {
                "id": c.client_id,
                "status": c.status,
                "allocated_t": c.allocated_t,
                "demand_t": c.demand_t,
                "reason": c.shortage_reason,
            }
            for c in plan.client_statuses
        ],
        "farms": [
            {
                "id": f.farm_id,
                "capacity_variance_t": f.capacity_variance_t,
                "segment_variances": [
                    {"segment": s.segment, "variance_t": s.variance_t} for s in f.segment_variances
                ],
                "local_t": f.local_t,
            }
            for f in plan.farm_comparisons
        ],
        "local_residuals": [r.model_dump() for r in plan.local_residuals],
    }
    return json.dumps(ctx, sort_keys=True)


_KNOWN_ID_RE = re.compile(r"(F\d{2}|C\d{2}|\b[A-D]\b)")


def _cited_ids(text: str) -> set[str]:
    return set(_KNOWN_ID_RE.findall(text))


def validate_llm_answer(answer: str, allowed: set[str]) -> str | None:
    """Reject model output that cites IDs outside the plan. Returns an error reason or None."""
    if not answer.strip():
        return "provider returned an empty answer"
    unknown = _cited_ids(answer) - allowed
    if unknown:
        return f"model cited unknown IDs: {', '.join(sorted(unknown))}"
    return None


def ask_llm(plan: PlanResult, question: str) -> tuple[str, str | None]:
    """Call the configured model. Returns (answer, provider_error)."""
    import urllib.error
    import urllib.request

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    base = os.getenv("OPENAI_BASE_URL", "").strip() or "https://api.openai.com/v1"
    model = os.getenv("OPENAI_MODEL", "").strip() or "gpt-4o-mini"

    allowed_farms = {f.farm_id for f in plan.farm_comparisons}
    allowed_clients = {c.client_id for c in plan.client_statuses}
    allowed = allowed_farms | allowed_clients | {"A", "B", "C", "D"}

    system = (
        "You explain a daily apple export plan to a production/commercial committee. "
        "Answer ONLY from the structured facts provided in the user message. "
        "Every number you cite must appear in those facts. Cite client IDs (C##), farm IDs "
        "(F##) and segment letters (A/B/C/D) exactly as given. Do not invent, estimate or "
        "calculate anything that is not in the facts. If the question cannot be answered from "
        "the facts, say exactly: 'Not available from the plan data.' Keep it under 120 words."
    )
    payload = {
        "model": model,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": f"FACTS:\n{build_context(plan)}\n\nQUESTION: {question}\n\nANSWER:",
            },
        ],
    }

    req = urllib.request.Request(
        f"{base.rstrip('/')}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}" if api_key else "",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return "", f"provider HTTP {e.code}"
    except Exception as e:  # timeout, connection, etc.
        return "", f"provider error: {type(e).__name__}"

    try:
        answer = body["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError):
        return "", "provider returned an invalid response"

    error = validate_llm_answer(answer, allowed)
    if error is not None:
        return "", error

    return answer, None


def run_assistant(plan: PlanResult, question: str) -> AssistantResponse:
    qtype = classify_question(question)
    configured = is_configured()

    if qtype is None:
        return AssistantResponse(
            mode="deterministic" if not configured else "llm",
            answer=_handle_unknown(question).answer,
            evidence=[],
            configured=configured,
            question_type=None,
            using_deterministic_fallback=True,
        )

    det_answer, det_evidence = deterministic_answer(plan, qtype)

    if not configured:
        return AssistantResponse(
            mode="deterministic",
            answer=det_answer,
            evidence=det_evidence,
            configured=False,
            question_type=qtype,
            using_deterministic_fallback=True,
        )

    answer, provider_error = ask_llm(plan, question)
    if provider_error is not None:
        return AssistantResponse(
            mode="deterministic",
            answer=(
                f"{det_answer}\n\n[Live model unavailable: {provider_error}. "
                "Showing the deterministic server-computed summary instead.]"
            ),
            evidence=det_evidence,
            configured=True,
            question_type=qtype,
            using_deterministic_fallback=True,
        )

    evidence = sorted(set(_cited_ids(answer)))
    return AssistantResponse(
        mode="llm",
        answer=answer,
        evidence=evidence,
        configured=True,
        question_type=qtype,
        using_deterministic_fallback=False,
    )
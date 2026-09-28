# Atlas Fresh — Daily Apple Export Planner

A browser-based **Production ↔ Commercial decision-support workspace** for the daily export
planning committee at Atlas Fresh (fictional). Given one daily snapshot (20 farms, 10 export
clients, one 500 t conditioning station), it:

1. **Loads & validates** the supplied workbook on the server (never mutates it),
2. **Compares** expected vs actual receipts by farm and quality segment (A/B/C/D),
3. **Plans** the deterministic farm-to-client export allocation,
4. **Decides** guardrails: client status (complete / partial / unserved), station use, export
   revenue and the low-value **local residual**,
5. **Explains** the plan with a grounded assistant that cites real farm/client/segment IDs.

This is a decision-support product for the Qarizmi weekend technical assessment. It prepares the
committee; it does **not** contact farms or clients, confirm the plan, or write to an external
system.

---

## Quick start (clean clone → running app)

Prerequisites: **Python 3.10+** and **Node 18+** (npm).

```bash
# 1. Backend: virtualenv + dependencies
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt

# 2. Frontend: install + production build (output in frontend/dist)
npm --prefix frontend install
npm --prefix frontend run build

# 3. Run the server (serves /api + the built frontend)
.venv/bin/uvicorn app.main:app --app-dir backend --port 8000

# 4. Open http://localhost:8000
```

Equivalent one-liner: `make setup && make run`. If the supplied workbook is not under
`data/Atlas_Fresh_Production_Commercial_Data.xlsx`, copy your copy of the packet file there or
set `ATLAS_DATA_PATH=/path/to/your.xlsx`. The workbook in `data/` is byte-for-byte the one from
the assessment pack; the source in `Assessment_Pack/` is never written to.

### Tests & build

```bash
make test    # pytest suite: policy, constraints, validation, API, AI boundaries
make build   # frontend production build
```

### Dev mode (hot reload)

```bash
make dev     # backend on :8000 (--reload) + Vite on :5173 proxying /api to :8000
```

---

## The five-step user journey

| Step | Where | What you see |
| --- | --- | --- |
| 1 · Load | *Today* banner | Server loads & validates the workbook; data-health line (20 farms, 10 clients, reference prices). Invalid input → error banner listing the sheet and offending ID (`Farms:F03`, `Clients:C04`, `Station:…`). |
| 2 · Compare | *Today* (chart) + **Production** tab | 600 t planned vs 560 t actual; segment bars expected vs actual; per-farm capacity & segment variances; residual local tonnes per farm. |
| 3 · Plan | **Commercial** tab | Every client shows rule (EXACT/MINIMUM A/B/C/D), demand, allocated, remaining, status and a **reason** for every shortfall. |
| 4 · Decide | **Allocation** tab | Traceable rows: farm ID → segment → client ID → tonnes → quality upgrade → export revenue. Local-market residual by farm/segment with its value impact. |
| 5 · Explain | **Assistant** panel | Answers grounded in the server result with cited IDs (deterministic summary without a key; optional live model, see below). |

The *Today* tab also draws the **Production → Commercial connection** (e.g. the Segment A
shortfall is what makes a high-value A client partial), plus export vs local capacity bars and a
KPI banner (export rate, local volume, export revenue, total value, at-risk clients).

---

## Deterministic planning policy (server-side)

Implemented verbatim in `backend/app/engine.py` per the brief:

1. Validate IDs, acceptance modes, segments and the complete reference-price table; expected mix
   fractions ∈ [0,1] and sum to 1.0 per farm.
2. Validate quantities: actual A/B/C/D, client demand and station capacity are non-negative
   multiples of 5 t; expected daily capacity may use one decimal.
3. Supply = each farm's **actual** tonnes (plans are for comparison only).
4. Clients processed by **export price descending**, ties by `client_id`.
5. Keep only compatible supply with a positive balance (EXACT = the segment only; MINIMUM = the
   requested segment or a better one).
6. Sort compatible supply by **smallest quality upgrade**, then **farm_id** (exact segment first,
   then one-level-better, etc. — matching “for MINIMUM C, prefer C before B or A”).
7. Allocate in **5 t steps** until demand, supply or station capacity is exhausted.
8. Unexported tonnes go local: `local value = residual × local ratio × segment reference price`.
9. Same input → same output. A client is COMPLETE when served == demand, PARTIAL when 0 < served <
   demand, UNSERVED when 0. At risk = partial + unserved. Shortfall reasons:
   `STATION_CAPACITY_REACHED` when capacity binds, `INSUFFICIENT_COMPATIBLE_SEGMENT` otherwise.

**Public baseline reproduced by the engine** (no hard-coding — the same code path is exercised by
tests that mutate input): 600 t plan · 560 t actual · 500 t export · 89.3% export rate ·
60 t local · €549,500 export revenue · €4,500 local value · €554,000 total · 3 at-risk clients
(C02, C09 partial via segment shortage; C08 partial via station capacity).

---

## Architecture

```
backend/                      Python 3.10 · FastAPI · openpyxl · pydantic
  app/
    main.py                   routes: /api/health, /api/seed, /api/plan, /api/assistant; serves frontend/dist
    loader.py                 xlsx parsing + strict business validation (tagged with sheet:ID)
    engine.py                 deterministic planning policy + KPIs/reasons/local residual
    ai.py                     grounded assistant: deterministic summary + optional model path
    segments.py               quality order, compatibility, upgrade distance
    schemas.py                typed response models (the exact JSON contract)
  tests/                      39 tests: engine (11), validation (13), API (5), AI (10)
frontend/                     React 18 + TypeScript + Vite (no UI/chart libs; inline SVG)
  src/components/             Overview, KpiBanner, charts, Production, Commercial, Allocation, Assistant
data/                         the supplied workbook (copy of the pack file, kept unchanged)
Makefile                      setup / test / build / run / dev
```

Design choices — see **Assumptions** below for the trade-offs.

---

## Grounded assistant

- **No key configured** → an honest, clearly labelled **deterministic server summary** computed
  from the same `PlanResult` the tables show. The UI says “deterministic (no key)”.
- **With a key / local endpoint** → a live LLM path via an OpenAI-compatible chat API. Enable it
  with environment variables (no paid service required — point `OPENAI_BASE_URL` at a local
  Ollama/llama.cpp gateway and it uses the local model):

  ```bash
  cp .env.example .env      # then edit .env
  make run                  # .env is loaded automatically at startup
  ```

  | Provider | `OPENAI_BASE_URL` | `OPENAI_MODEL` |
  |---|---|---|
  | Google Gemini | `https://generativelanguage.googleapis.com/v1beta/openai` | `gemini-3.8-flash` |
  | OpenAI | *(leave empty)* | `gpt-4o-mini` |
  | Ollama (local) | `http://localhost:11434/v1` | `llama3.1` |

  Only `OPENAI_API_KEY` is required; take a Gemini key from
  <https://aistudio.google.com/apikey>. Gemini is reached through its
  OpenAI-compatible endpoint, so no code change or extra dependency is needed.
  `.env` is read by `python-dotenv` at startup, and real environment variables
  take precedence over it.

- **Boundaries (enforced):** the model receives only a minimal structured context; cited IDs are
  regex-validated against the actual farm/client/segment sets — output citing unknown IDs is
  rejected and falls back to the deterministic summary. Unsupported questions and provider/timeout
  failures are answered honestly. The assistant never calculates, reallocates or writes anything.

---

## Validation & failure UX

Every route returns either a typed result or an `error` + `issues[]` payload where each issue is
`{location, message}` (e.g. `Clients:C04`, “demand_t=13 is not a multiple of 5 t”). The frontend
renders these in an error banner with a **Try again** button, and shows explicit loading and empty
states. The source workbook is never modified.

---

## Assumptions, limitations & omissions (transparency)

**What works & is tested**
- Exact reference-policy allocation with deterministic ordering/compatibility/limits, the full
  baseline, invariant checks (`export ≤ capacity`, `client export ≤ demand`, `farm-segment export ≤
  actual`, compatibility, `export + local = actual`) and local-value math.
- All validation rules from the brief (duplicate/missing IDs, reference prices, mix ranges/sum,
  non-5 t quantities, negative values, invalid capacity/mode/segment). Evaluators can change any
  valid input and the output recomputes — nothing is hard-coded.
- 39 automated tests + a full API/SPA smoke test (baseline KPIs and reasons confirmed via curl).

**Intentional simplifications**
- Single daily snapshot, no persistence (explicitly out of scope). The workbook is loaded on each
  plan; a file this size makes caching unnecessary, but an in-memory cache keyed by path is in
  place for the seed route.
- “Quality upgrade” is reported as an integer level above the requested segment (0 = exact). For
  MINIMUM clients we prefer the exact segment before better ones, per the brief's example
  (“for MINIMUM C, prefer C before B or A”).
- The live-model path is provided but not required and not part of the core run — this keeps the
  clean-clone experience free of API keys and networks.
- No auth, DB, Docker or CI (non-requirements for this exercise).

**Next three production steps**
1. **Multi-day view**: persist each day's snapshot + committee decisions, and add day-over-day
   trend KPIs (export-rate drift, segment shortfall hotspots) with a capacity-scenario UI.
2. **Approval workflow**: an explicit “approve plan” step that writes a frozen operating plan and
   the audit trail (farm↔client↔segment per day), still read-only for the AI.
3. **Exceptions table**: rank the week's worst farm-segment gaps and at-risk orders, plus a
   capacity-what-if comparison (e.g. +50 t to station) computed with the same deterministic engine.

---

## AI tooling disclosure (as required)

- **Assistants of code:** this project was built with the opencode coding agent (model
  `big-pickle`). It drafted the backend engine, loader, schemas, frontend components and README;
  I reviewed and corrected its test expectations, ran the full suite, and verified the live API
  output against the public baseline numbers before submission.
- **LLM in the product itself:** the *planning assistant* uses a hosted/local model only when an
  endpoint is configured; by default it returns a deterministic server summary. The LLM never
  computes allocations or KPIs (explicitly forbidden by the brief).
- **Data:** all figures are synthetic and supplied by Qarizmi; no secrets or client data are
  included.
- **Time spent:** ~9 hours across planning, implementation, testing, verification and docs.
- **Walkthrough video:** (add your Loom/other URL here)

<sub>Deliverables: repository (this), README, 39 tests, baseline parity, grounded assistant, honest fallbacks.</sub>
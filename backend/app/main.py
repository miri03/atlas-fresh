"""Atlas Fresh — Daily Export Planner · API entrypoint.

Runs the whole workspace: workbook load + strict validation, the
deterministic planning engine, and the grounded assistant. The frontend
build is served from `frontend/dist` when present.
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .engine import run_plan

from .schemas import DataHealth, ErrorResponse, PlanResult, WorkbookData
from .loader import WorkbookValidationError, build_data_health, load_workbook

ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_DATA_PATH = Path(os.getenv("ATLAS_DATA_PATH", ROOT / "data" / "Atlas_Fresh_Production_Commercial_Data.xlsx"))
FRONTEND_DIST = ROOT / "frontend" / "dist"

app = FastAPI(
    title="Atlas Fresh — Daily Export Planner",
    version="1.0.0",
    description="Production–Commercial decision-support workspace for the daily apple export plan.",
)

_CACHE: dict[str, WorkbookData] = {}

def _get_data() -> WorkbookData:
    path = str(DEFAULT_DATA_PATH)
    if path in _CACHE:
        return _CACHE[path]
    data = load_workbook(path)
    _CACHE[path] = data
    return data

def _error(status: int, error: str, detail: str | None = None, issues: list[tuple[str, str]] | None = None) -> HTTPException:
    payload = ErrorResponse(
        error=error,
        detail=detail,
        issues=[{"location": loc, "message": msg} for loc, msg in (issues or [])],
    )
    return HTTPException(status_code=status, detail=payload.model_dump())

@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}

@app.post("/api/seed", response_model=DataHealth)
def seed() -> DataHealth:
    """Load and validate the supplied workbook (server-side)."""
    try:
        data = load_workbook(DEFAULT_DATA_PATH)
        _CACHE[str(DEFAULT_DATA_PATH)] = data
        return DataHealth(**build_data_health(data))
    except WorkbookValidationError as e:
        raise _error(422, "workbook_invalid", "The workbook did not pass business validation.", e.issues)
    except Exception as e:  # corrupt file, missing sheet, etc.
        raise _error(500, "workbook_load_failed", f"Could not load workbook: {e}")

@app.post("/api/plan", response_model=PlanResult)
def plan() -> PlanResult:
    """Compute the deterministic daily allocation for the loaded workbook."""
    try:
        data = _get_data()
    except WorkbookValidationError as e:
        raise _error(422, "workbook_invalid", "The workbook did not pass business validation.", e.issues)
    except Exception as e:
        raise _error(500, "workbook_load_failed", f"Could not load workbook: {e}")
    return run_plan(data)


# ---------------------------------------------------------------------------
# Frontend (static build served from frontend/dist)
# ---------------------------------------------------------------------------


@app.exception_handler(HTTPException)
async def http_exception_handler(_, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content=exc.detail)


def mount_frontend(route_app: FastAPI) -> None:
    if FRONTEND_DIST.is_dir():
        route_app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

        @route_app.get("/{full_path:path}", include_in_schema=False)
        def spa(full_path: str):
            candidate = FRONTEND_DIST / full_path
            if full_path and candidate.is_file():
                return FileResponse(candidate)
            index = FRONTEND_DIST / "index.html"
            return FileResponse(index) if index.exists() else JSONResponse(
                status_code=404, content={"error": "frontend_not_built", "detail": "Run the frontend build, or use only /api routes."}
            )
    else:
        @route_app.get("/", include_in_schema=False)
        def no_frontend():
            return JSONResponse(
                status_code=404,
                content={
                    "error": "frontend_not_built",
                    "detail": "frontend/dist is missing. Build the frontend first (see README) or use /api endpoints.",
                },
            )


mount_frontend(app)
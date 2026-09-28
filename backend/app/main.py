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
from dotenv import load_dotenv

from . import ai
from .engine import run_plan
from .loader import WorkbookValidationError, build_data_health, load_workbook
from .schemas import AssistantRequest, AssistantResponse, DataHealth, ErrorResponse, PlanResult, WorkbookData

ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(ROOT / ".env")

# Some Python builds (notably the python.org framework on macOS) ship without a
# readable default CA bundle, which makes every outbound HTTPS call fail with
# CERTIFICATE_VERIFY_FAILED. certifi is already installed as an httpx
# dependency, so point OpenSSL at its bundle unless the user set SSL_CERT_FILE.
if "SSL_CERT_FILE" not in os.environ:
    try:
        import certifi

        os.environ["SSL_CERT_FILE"] = certifi.where()
    except ImportError:
        pass

_data_path = Path(os.getenv("ATLAS_DATA_PATH", ROOT / "data" / "Atlas_Fresh_Production_Commercial_Data.xlsx"))
DEFAULT_DATA_PATH = _data_path if _data_path.is_absolute() else ROOT / _data_path
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
    return {"status": "ok", "assistant_configured": ai.is_configured()}

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


@app.post("/api/assistant", response_model=AssistantResponse)
def assistant(req: AssistantRequest) -> AssistantResponse:
    """Grounded explanation of the computed plan (read-only)."""
    data = _get_data()
    plan_result = run_plan(data)
    return ai.run_assistant(plan_result, req.question)


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
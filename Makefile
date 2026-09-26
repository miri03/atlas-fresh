.PHONY: setup test build run dev clean frontend-install

PY := .venv/bin/python
PIP := .venv/bin/pip
UVICORN := .venv/bin/uvicorn
FRONTEND := frontend

## One clean-start path from a fresh clone
setup:
	python3 -m venv .venv
	$(PIP) install --upgrade pip
	$(PIP) install -r backend/requirements.txt
	npm --prefix $(FRONTEND) install
	npm --prefix $(FRONTEND) run build
	@echo
	@echo "Done. Start the app with:  make run"

## Run the automated test suite (planning policy, validation, API, AI boundaries)
test:
	$(PY) -m pytest backend/tests -q

## Build the frontend into frontend/dist (served by the backend)
build:
	npm --prefix $(FRONTEND) run build

## Run the full app on http://localhost:8000
run:
	$(UVICORN) app.main:app --app-dir backend --port 8000

## Dev mode: backend on 8000 + Vite dev server on 5173 (with /api proxy)
dev:
	$(UVICORN) app.main:app --app-dir backend --port 8000 --reload &
	npm --prefix $(FRONTEND) run dev

clean:
	rm -rf .venv $(FRONTEND)/node_modules $(FRONTEND)/dist __pycache__ backend/**/__pycache__ backend/**/.pytest_cache
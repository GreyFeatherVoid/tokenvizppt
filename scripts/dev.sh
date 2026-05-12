#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
CONDA_ENV="${CONDA_ENV:-tokenvizppt}"

API_PID=""
WORKER_PID=""
FRONTEND_PID=""

cleanup() {
  echo
  echo "[dev] stopping app processes..."
  for pid in "$FRONTEND_PID" "$WORKER_PID" "$API_PID"; do
    if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
    fi
  done
  wait 2>/dev/null || true
}

trap cleanup EXIT INT TERM

if ! command -v conda >/dev/null 2>&1; then
  echo "[dev] conda is required but was not found in PATH." >&2
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "[dev] docker is required but was not found in PATH." >&2
  exit 1
fi

echo "[dev] starting postgres and redis with docker compose..."
cd "$ROOT_DIR"
docker compose up -d postgres redis

echo "[dev] running database migrations..."
cd "$BACKEND_DIR"
conda run -n "$CONDA_ENV" alembic upgrade head

echo "[dev] starting FastAPI on http://localhost:8000 ..."
conda run --no-capture-output -n "$CONDA_ENV" \
  python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 &
API_PID=$!

echo "[dev] starting Celery worker..."
conda run --no-capture-output -n "$CONDA_ENV" \
  python -m celery -A app.workers.celery_app.celery_app worker --loglevel=info &
WORKER_PID=$!

echo "[dev] starting Vite frontend on http://localhost:5173 ..."
cd "$FRONTEND_DIR"
npm run dev -- --host 0.0.0.0 &
FRONTEND_PID=$!

echo
echo "[dev] all services started."
echo "[dev] frontend: http://localhost:5173"
echo "[dev] api:      http://localhost:8000/api/health"
echo "[dev] db:       http://localhost:8000/api/health/db"
echo "[dev] press Ctrl+C to stop API, worker, and frontend."

wait

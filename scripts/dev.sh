#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
CONDA_ENV="${CONDA_ENV:-tokenvizppt}"
CONDA_ROOT="${CONDA_ROOT:-$HOME/miniconda3}"

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

if ! command -v conda >/dev/null 2>&1 && [[ -x "$CONDA_ROOT/bin/conda" ]]; then
  export PATH="$CONDA_ROOT/bin:$CONDA_ROOT/condabin:$PATH"
fi

if ! command -v conda >/dev/null 2>&1; then
  echo "[dev] conda is required but was not found in PATH." >&2
  echo "[dev] set CONDA_ROOT=/path/to/miniconda or initialize conda in this shell." >&2
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "[dev] docker is required but was not found in PATH." >&2
  exit 1
fi

echo "[dev] starting postgres and redis with docker compose..."
cd "$ROOT_DIR"
if docker ps >/dev/null 2>&1; then
  docker compose up -d postgres redis
elif command -v sg >/dev/null 2>&1 && getent group docker >/dev/null 2>&1; then
  sg docker -c "cd '$ROOT_DIR' && docker compose up -d postgres redis"
else
  echo "[dev] docker is installed, but this shell cannot access the Docker daemon." >&2
  echo "[dev] try: newgrp docker  # or reconnect SSH, then rerun ./scripts/dev.sh" >&2
  exit 1
fi

echo "[dev] running database migrations..."
cd "$BACKEND_DIR"
conda run -n "$CONDA_ENV" alembic upgrade head

echo "[dev] starting FastAPI on http://localhost:6001 ..."
conda run --no-capture-output -n "$CONDA_ENV" \
  python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 6001 &
API_PID=$!

echo "[dev] starting Celery worker..."
conda run --no-capture-output -n "$CONDA_ENV" \
  python -m celery -A app.workers.celery_app.celery_app worker --loglevel=info &
WORKER_PID=$!

echo "[dev] starting Vite frontend on http://localhost:6080 ..."
cd "$FRONTEND_DIR"
npm run dev -- --host 0.0.0.0 --port 6080 &
FRONTEND_PID=$!

echo
echo "[dev] all services started."
echo "[dev] frontend: http://localhost:6080"
echo "[dev] api:      http://localhost:6001/api/health"
echo "[dev] db:       http://localhost:6001/api/health/db"
echo "[dev] press Ctrl+C to stop API, worker, and frontend."

wait

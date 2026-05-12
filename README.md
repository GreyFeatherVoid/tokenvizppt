# tokenvizPPT

Web-first AI PPT generation and editing application.

This project is a clean implementation. It does not modify or reuse files from `oh-my-ppt`.

## Current Status

The repository currently contains the Phase 0 skeleton:

- React + Vite frontend.
- FastAPI backend.
- Conda Python 3.12 environment named `tokenvizppt`.
- Basic health API.
- File-backed create-session API.
- File-backed generation-start API.
- SSE progress stream.
- Cloud-LLM slide planning with deterministic fallback.
- Deterministic HTML slide rendering.
- Browser preview after generation completes.

## Backend Setup

The Conda environment has already been created locally:

```bash
conda activate tokenvizppt
```

Install backend dependencies:

```bash
cd backend
pip install -e .[dev]
npm install
cp .env.example .env
```

The backend `npm install` is used by the editable PPTX exporter. The export path first tries
`dom-to-pptx` for higher-fidelity editable PowerPoint output and falls back to the Python exporter
if that conversion fails.

## One-Command Development

Recommended local startup:

```bash
cd /home/duoduo/Documents/claude_project/ppt_generate/tokenvizPPT
./scripts/dev.sh
```

This starts:

- Docker PostgreSQL on `localhost:15432`
- Docker Redis on `localhost:16379`
- FastAPI on `http://localhost:8000`
- Celery worker
- Vite frontend on `http://localhost:5173`

Press `Ctrl+C` to stop the API, worker, and frontend. Docker services stay running so subsequent
starts are faster.

Stop Docker services when needed:

```bash
docker compose down
```

## Manual Backend Startup

Start the API in one terminal:

```bash
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Start the Celery worker in another terminal:

```bash
cd backend
conda activate tokenvizppt
python -m celery -A app.workers.celery_app.celery_app worker --loglevel=info
```

Health check:

```bash
curl http://localhost:8000/api/health
```

## Database Setup

Phase 2 adds PostgreSQL and Redis infrastructure. The current generation flow still uses local
file-backed storage until the database-backed repository is wired in.

Start local services:

```bash
cd /home/duoduo/Documents/claude_project/ppt_generate/tokenvizPPT
docker compose up -d postgres redis
```

The compose services intentionally use uncommon host ports to avoid conflicts with local services:

```text
PostgreSQL: localhost:15432 -> container:5432
Redis:      localhost:16379 -> container:6379
```

Run migrations:

```bash
cd backend
conda activate tokenvizppt
alembic upgrade head
```

Check database mirror counts after generating a deck:

```bash
curl http://localhost:8000/api/health/db
```

## Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Open:

```text
http://localhost:5173
```

The Vite dev server proxies `/api` to `http://localhost:8000`.

## Phase 1 Behavior

Generation tries the backend-configured cloud LLM first. If the model is not configured or returns
invalid JSON, it falls back to the deterministic local planner so the main flow remains testable.
It writes session metadata and generated slide HTML under:

```text
storage/sessions/
```

This keeps the first web loop testable before adding PostgreSQL and Celery.

## Model Configuration

The frontend must remain model-agnostic. LLM configuration is backend-only through environment variables:

```bash
TOKENVIZPPT_LLM_PROVIDER=openai
TOKENVIZPPT_LLM_MODEL=gpt-4o-mini
TOKENVIZPPT_LLM_API_KEY=...
TOKENVIZPPT_LLM_BASE_URL=
```

Local model support is intentionally excluded.

Config location:

```text
backend/.env
```

Create it from the example:

```bash
cd backend
cp .env.example .env
```

For official OpenAI, leave `TOKENVIZPPT_LLM_BASE_URL` empty. For OpenAI-compatible cloud providers,
set `TOKENVIZPPT_LLM_BASE_URL` to the provider's `/v1` endpoint, for example:

```bash
TOKENVIZPPT_LLM_BASE_URL=https://api.deepseek.com/v1
```

Restart the backend after changing `.env`.

## AI Image Configuration

AI image generation is backend-only and disabled by default. Configure it in `backend/.env`:

```bash
TOKENVIZPPT_AI_IMAGE_ENABLED=true
TOKENVIZPPT_AI_IMAGE_PROVIDER=openai
TOKENVIZPPT_AI_IMAGE_MODEL=gpt-image-2
TOKENVIZPPT_AI_IMAGE_API_KEY=...
TOKENVIZPPT_AI_IMAGE_BASE_URL=https://your-compatible-image-api/v1
TOKENVIZPPT_AI_IMAGE_DEFAULT_SIZE=1536x1024
TOKENVIZPPT_AI_IMAGE_MAX_PER_DECK=2
```

Generated images are intended as sparse visual anchors, not filler. The slide generation flow should
decide that a specific page needs an AI image before the image API is called. Search-image
integration is deferred because copyright, attribution, and quality risks are higher.

## LLM Diagnostics

To reproduce slow/504 behavior with the current business HTML prompt:

```bash
cd backend
conda activate tokenvizppt
python scripts/reproduce_504.py --attempts 3 --concurrency 1 --timeout 120
```

To test whether concurrency increases failures:

```bash
python scripts/reproduce_504.py --attempts 4 --concurrency 2 --timeout 120
```

## Implementation Plan

See [docs/plan.md](docs/plan.md).

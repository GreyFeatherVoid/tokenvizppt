# tokenvizPPT

tokenvizPPT is a web PPT generator for creating, editing, and exporting editable PowerPoint decks from prompts and uploaded files.

The frontend handles the creation workflow. Model calls, API keys, file parsing, asset storage, background jobs, and PPTX export stay in the Python backend.

## Features

- Generate PPT decks from prompts, style skills, and uploaded files.
- Upload txt, md, csv, pdf, docx, xlsx, and images as generation context.
- Analyze uploaded images with a vision-capable model.
- Optionally generate AI visuals when a slide genuinely needs one.
- Edit slides, text, images, and rollback versions.
- Keep local deck history without login.
- Export editable `.pptx` files.
- Switch UI language between English and Chinese.

## Stack

```text
frontend/          React + Vite
backend/           FastAPI + Celery + SQLAlchemy + python-pptx
docker-compose.yml PostgreSQL + Redis
storage/           uploaded files, generated assets, exported PPTX files
```

## Local Development

Requirements:

- Python 3.12
- Node.js 20+
- Docker and Docker Compose

Install dependencies:

```bash
cd backend
cp .env.example .env
python -m pip install -e .[dev]
npm install

cd ../frontend
npm install
```

Edit `backend/.env`:

```bash
TOKENVIZPPT_LLM_MODEL=your-model
TOKENVIZPPT_LLM_API_KEY=your-key
TOKENVIZPPT_LLM_BASE_URL=https://your-openai-compatible-api/v1
```

Start everything:

```bash
cd /path/to/tokenvizPPT
./scripts/dev.sh
```

Development URLs:

```text
Frontend:   http://localhost:5173
FastAPI:    http://localhost:8000
PostgreSQL: localhost:15432
Redis:      localhost:16379
```

Health checks:

```bash
curl http://localhost:8000/api/health
curl http://localhost:8000/api/health/db
```

## Configuration

All model configuration is backend-only. Never put API keys in frontend code.

Common `backend/.env` values:

```bash
TOKENVIZPPT_APP_ENV=development
TOKENVIZPPT_DATABASE_URL=postgresql+psycopg://tokenvizppt:tokenvizppt@localhost:15432/tokenvizppt
TOKENVIZPPT_REDIS_URL=redis://localhost:16379/0
TOKENVIZPPT_STORAGE_ROOT=../storage
TOKENVIZPPT_CORS_ORIGINS=["http://localhost:5173"]

TOKENVIZPPT_LLM_PROVIDER=openai
TOKENVIZPPT_LLM_MODEL=your-model
TOKENVIZPPT_LLM_API_KEY=your-key
TOKENVIZPPT_LLM_BASE_URL=https://your-openai-compatible-api/v1
TOKENVIZPPT_LLM_TIMEOUT_SECONDS=120

TOKENVIZPPT_GENERATION_SLIDE_CONCURRENCY=3
TOKENVIZPPT_IMAGE_ANALYSIS_CONCURRENCY=3
```

Optional AI image generation:

```bash
TOKENVIZPPT_AI_IMAGE_ENABLED=true
TOKENVIZPPT_AI_IMAGE_MODEL=gpt-image-2
TOKENVIZPPT_AI_IMAGE_API_KEY=your-image-key
TOKENVIZPPT_AI_IMAGE_BASE_URL=https://your-image-api
TOKENVIZPPT_AI_IMAGE_MAX_PER_DECK=2
```

## Server Deployment

Recommended production layout:

```text
Browser -> http://SERVER_IP:6000
Nginx :6000 -> frontend/dist
Nginx /api/* -> FastAPI 127.0.0.1:6001
PostgreSQL and Redis -> local only
Celery worker -> background generation/export jobs
```

Only expose `6000` publicly. Do not expose `6001`, `15432`, or `16379`.

### 1. Prepare

```bash
sudo apt update
sudo apt install -y git nginx docker.io docker-compose-plugin python3.12 python3.12-venv nodejs npm

git clone git@github.com:GreyFeatherVoid/tokenvizppt.git
cd tokenvizppt
```

Use Node.js 20+ if the distro package is old.

### 2. Configure

```bash
cd backend
cp .env.example .env
```

Set production values:

```bash
TOKENVIZPPT_APP_ENV=production
TOKENVIZPPT_DATABASE_URL=postgresql+psycopg://tokenvizppt:tokenvizppt@localhost:15432/tokenvizppt
TOKENVIZPPT_REDIS_URL=redis://localhost:16379/0
TOKENVIZPPT_STORAGE_ROOT=../storage
TOKENVIZPPT_CORS_ORIGINS=["http://SERVER_IP:6000"]
TOKENVIZPPT_LLM_MODEL=your-model
TOKENVIZPPT_LLM_API_KEY=your-key
TOKENVIZPPT_LLM_BASE_URL=https://your-openai-compatible-api/v1
```

### 3. Install And Build

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .[dev]
npm install

cd ../frontend
npm install
npm run build
```

### 4. Start Data Services

```bash
cd /path/to/tokenvizppt
docker compose up -d postgres redis

cd backend
source .venv/bin/activate
alembic upgrade head
```

### 5. Start App Services

API:

```bash
cd backend
source .venv/bin/activate
python -m uvicorn app.main:app --host 127.0.0.1 --port 6001
```

Worker:

```bash
cd backend
source .venv/bin/activate
python -m celery -A app.workers.celery_app.celery_app worker --loglevel=info
```

For real deployment, run both commands with `systemd`, `supervisor`, or another process manager.

### 6. Configure Nginx

Create `/etc/nginx/sites-available/tokenvizppt`:

```nginx
server {
    listen 6000;
    server_name _;

    client_max_body_size 100M;

    location / {
        root /path/to/tokenvizppt/frontend/dist;
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:6001/api/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_buffering off;
        proxy_read_timeout 600s;
        proxy_send_timeout 600s;
    }
}
```

Enable:

```bash
sudo ln -s /etc/nginx/sites-available/tokenvizppt /etc/nginx/sites-enabled/tokenvizppt
sudo nginx -t
sudo systemctl reload nginx
sudo ufw allow 6000/tcp
```

Check:

```text
http://SERVER_IP:6000
http://SERVER_IP:6000/api/health
```

## Deployment Checklist

- `backend/.env` exists and is not committed.
- PostgreSQL and Redis are running.
- `alembic upgrade head` completed.
- `frontend/dist` exists.
- FastAPI responds at `127.0.0.1:6001/api/health`.
- Nginx responds at `SERVER_IP:6000/api/health`.
- Browser upload, generation, history, and PPTX export work.

## Plan

See [docs/plan.md](docs/plan.md).

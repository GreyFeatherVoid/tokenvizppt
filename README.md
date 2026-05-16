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
- Conda environment named `tokenvizppt` when using `scripts/dev.sh`

Install dependencies:

```bash
conda activate tokenvizppt

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
Frontend:   http://localhost:6080
FastAPI:    http://localhost:6001
PostgreSQL: localhost:15432
Redis:      localhost:16379
```

Health checks:

```bash
curl http://localhost:6001/api/health
curl http://localhost:6001/api/health/db
```

## Configuration

All model configuration is backend-only. Never put API keys in frontend code.

Common `backend/.env` values:

```bash
TOKENVIZPPT_APP_ENV=development
TOKENVIZPPT_DATABASE_URL=postgresql+psycopg://tokenvizppt:tokenvizppt@localhost:15432/tokenvizppt
TOKENVIZPPT_REDIS_URL=redis://localhost:16379/0
TOKENVIZPPT_STORAGE_ROOT=../storage
TOKENVIZPPT_CORS_ORIGINS=["http://localhost:6080"]

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
Browser -> https://ppt.forgespark.org
Nginx 80/443 -> frontend/dist
Nginx /api/* -> FastAPI 127.0.0.1:6001
PostgreSQL and Redis -> local only
Celery worker -> systemd service for generation/export jobs
```

Only expose `80` and `443` publicly for web traffic. Do not expose `6001`, `15432`, or `16379`.

`80` and `443` can be shared by multiple projects through Nginx `server_name` rules. They do not have to be reserved for this project only.

### 1. Prepare

```bash
sudo apt update
sudo apt install -y git nginx docker.io docker-compose-plugin nodejs npm

git clone git@github.com:GreyFeatherVoid/tokenvizppt.git
cd tokenvizppt
```

Use Node.js 20+ if the distro package is old. The current server uses a conda environment at `/home/ubuntu/miniconda3/envs/tokenvizppt`.

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
TOKENVIZPPT_PUBLIC_BASE_URL=https://ppt.forgespark.org
TOKENVIZPPT_CORS_ORIGINS=["https://ppt.forgespark.org"]
TOKENVIZPPT_AUTH_COOKIE_SECURE=true
TOKENVIZPPT_LLM_MODEL=your-model
TOKENVIZPPT_LLM_API_KEY=your-key
TOKENVIZPPT_LLM_BASE_URL=https://your-openai-compatible-api/v1
```

### 3. Install And Build

```bash
conda activate tokenvizppt

cd backend
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
conda activate tokenvizppt
alembic upgrade head
```

### 5. Install systemd Services

The production server uses systemd for the FastAPI API and Celery worker. This is more reliable than `nohup`, `tmux`, or running `scripts/dev.sh` as a background process.

The included service files assume:

```text
Project path: /home/ubuntu/tokenvizppt
Python path:  /home/ubuntu/miniconda3/envs/tokenvizppt/bin/python
Run user:     ubuntu
```

Edit `deploy/systemd/tokenvizppt-api.service` and `deploy/systemd/tokenvizppt-worker.service` first if your server uses different paths.

```bash
cd /path/to/tokenvizppt
sudo cp deploy/systemd/tokenvizppt-api.service /etc/systemd/system/tokenvizppt-api.service
sudo cp deploy/systemd/tokenvizppt-worker.service /etc/systemd/system/tokenvizppt-worker.service
sudo systemctl daemon-reload
sudo systemctl enable --now tokenvizppt-api tokenvizppt-worker
```

Restart backend services after backend code or `backend/.env` changes:

```bash
sudo systemctl restart tokenvizppt-api tokenvizppt-worker
```

Check status:

```bash
sudo systemctl status tokenvizppt-api tokenvizppt-worker
```

Follow logs:

```bash
sudo journalctl -u tokenvizppt-api -f
sudo journalctl -u tokenvizppt-worker -f
```

### 6. Configure Nginx

Create `/etc/nginx/sites-available/tokenvizppt`:

```nginx
server {
    listen 80;
    listen [::]:80;
    server_name ppt.forgespark.org;

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
```

### 7. Enable HTTPS

Use Certbot to request and auto-renew a free Let's Encrypt certificate:

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d ppt.forgespark.org --redirect
sudo certbot renew --dry-run --no-random-sleep-on-renew
```

The certbot timer should be active:

```bash
systemctl list-timers --all | grep certbot
```

Check:

```bash
curl https://ppt.forgespark.org/api/health
curl -I http://ppt.forgespark.org
```

The HTTP check should return a `301` redirect to HTTPS.

### 8. Frontend Updates

The production frontend is served from `frontend/dist` by Nginx. After frontend code changes, rebuild it:

```bash
cd /path/to/tokenvizppt/frontend
npm run build
```

Nginx usually does not need a reload after rebuilding static files. Reload Nginx only after changing Nginx config:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

## Deployment Checklist

- `backend/.env` exists and is not committed.
- PostgreSQL and Redis are running.
- `alembic upgrade head` completed.
- `frontend/dist` exists.
- FastAPI responds at `127.0.0.1:6001/api/health`.
- Nginx responds at `https://ppt.forgespark.org/api/health`.
- `tokenvizppt-api` and `tokenvizppt-worker` are active.
- Certbot renewal dry-run succeeds.
- Browser upload, generation, history, and PPTX export work.

## Plan

See [docs/plan.md](docs/plan.md).

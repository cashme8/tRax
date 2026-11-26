# tRax

Tax compliance for Rwandan companies and their accountants: record invoices, purchases and
expenses, calculate RRA taxes, track filing deadlines and prepare returns.

> **Status:** Milestone 1 in progress. tRax prepares figures; the company or its accountant
> reviews and files every return. Seeded tax rates must be verified with RRA.

## Repository layout

```
backend/            Django project (API, tax engine, Celery worker)
  config/           settings, URLs, Celery app
frontend/           Next.js app (TypeScript, Tailwind, shadcn/ui)
docker-compose.yml  local dev stack
.env.example        template for your local .env
CLAUDE.md           architecture rules and decisions
```

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (on Windows, with WSL 2)
- Git
- Optional, for editor support outside Docker: Node.js 24

## First-time setup

```bash
# 1. Create your local environment file (git-ignored)
cp .env.example .env            # PowerShell: Copy-Item .env.example .env

# 2. Build the images and start everything
docker compose up --build
```

Then open:

| What | URL |
|---|---|
| Frontend | http://localhost:3000 |
| API health check | http://localhost:8000/api/health/ → `{"status": "ok"}` |
| Django admin (staff only) | http://localhost:8000/admin/ |

Create an admin user (after Step 2 adds the custom user model):

```bash
docker compose run --rm backend python manage.py createsuperuser
```

## Everyday commands

```bash
docker compose up                                    # start the stack
docker compose down                                  # stop it (data is kept)
docker compose down -v                               # stop and DELETE the database

docker compose run --rm backend pytest               # backend tests
docker compose run --rm backend pytest --create-db   # rebuild the test DB after model changes
docker compose run --rm backend ruff check .         # lint Python
docker compose run --rm backend python manage.py makemigrations
docker compose run --rm backend python manage.py migrate

docker compose run --rm frontend npm run lint        # ESLint
docker compose run --rm frontend npm run typecheck   # TypeScript strict check
```

If you add a dependency, rebuild: `docker compose build backend` or `docker compose build frontend`.

## Services

| Service | What it runs | Port |
|---|---|---|
| postgres | PostgreSQL 16 | 5432 |
| redis | Redis 7 (Celery message broker) | 6379 |
| backend | Django dev server; runs migrations on start | 8000 |
| worker | Celery worker (background jobs) | — |
| frontend | Next.js dev server | 3000 |

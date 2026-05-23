# HackathonFeed Backend

Production REST API for the HackathonFeed platform. Sits on top of the existing Supabase `hackathons` table populated by the scraper pipeline.

## Architecture

```text
Frontend → FastAPI Routes → Services → Repositories → Supabase/PostgreSQL
```

## Quick Start

1. Copy environment file:

```bash
cp .env.example .env
```

2. Set `DATABASE_URL` to your Supabase PostgreSQL connection string and configure JWT secrets.

3. Install dependencies with [uv](https://docs.astral.sh/uv/):

```bash
uv sync
```

4. Run database migrations (creates `users`, `bookmarks`, `analytics_events`, `search_logs`):

```bash
uv run alembic upgrade head
```

5. Start the API:

```bash
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open Swagger docs at `http://localhost:8000/docs`.

## API Overview

| Area | Endpoints |
|---|---|
| Auth | `POST /api/v1/auth/register`, `/login`, `/refresh`, `GET /me` |
| Users | `GET/PATCH /api/v1/users/me` |
| Hackathons | `GET /api/v1/hackathons`, `/search`, `/trending`, `/{id}` |
| Bookmarks | `POST/GET/DELETE /api/v1/bookmarks` |
| Themes | `GET /api/v1/themes`, `/themes/platforms` |
| Trends | `GET /api/v1/trends/hackathons`, `/themes`, `/platforms` |
| Admin | `GET /api/v1/admin/stats`, `POST /scrape`, `DELETE /hackathon/{id}` |

All successful responses follow:

```json
{
  "success": true,
  "message": "...",
  "data": {}
}
```

## Project Structure

- `app/api/` – HTTP routes and dependencies
- `app/services/` – business logic
- `app/repositories/` – database access
- `app/models/` – SQLAlchemy ORM models
- `app/schemas/` – Pydantic DTOs
- `app/core/` – config, security, database, logging
- `app/middleware/` – logging and rate limiting

## Notes

- The `hackathons` table is owned by the scraper; this backend reads it and adds user-facing features.
- Redis caching and background analytics jobs can be wired through APScheduler in a later phase.
- Create an admin user by updating the `role` column in Supabase after registration.

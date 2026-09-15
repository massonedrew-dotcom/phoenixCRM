# Architecture

## Stack

- Backend: Python 3.12, FastAPI, SQLAlchemy 2.0 (async), Alembic, Pydantic v2
- DB: PostgreSQL 16 with `pg_trgm`
- Auth: JWT (access + refresh), passwords hashed with argon2
- Images: Pillow (+ pillow-heif) for thumbnails; ffmpeg optional for video posters
- Frontend: React 18 + Vite + TypeScript, TanStack Query, React Router
- Reverse proxy and static/media serving: nginx
- Packaging: Docker Compose

Rationale: the deployment target is undecided (agency's own server now, possibly
a VPS later). Docker Compose makes all three targets identical. FastAPI serving
pure JSON keeps the door open for the Telegram Mini App without a rewrite.

## Layers

```
backend/
  app/
    api/            FastAPI routers — HTTP only, no business logic
    schemas/        Pydantic request/response models
    services/       business logic, transactions, permission checks
    repositories/   SQLAlchemy queries
    models/         ORM models
    core/           config, security, dependencies, exceptions
    storage/        file storage abstraction
    audit/          audit middleware and helpers
    cli.py          create-admin, seed-districts
  migrations/       Alembic
  scripts/          benchmark seed and EXPLAIN check (never run against real data)
  tests/
frontend/           React + Vite app
nginx/              reverse proxy configuration and image
backup/             nightly pg_dump job
docker-compose.yml
```

Rules:
- Routers never touch the ORM directly.
- Permission checks live in `services/`, never in the frontend and never in
  routers. A missing check in a service is a security bug.
- Repositories return ORM objects or scalars; services return schemas.

## File storage abstraction

```python
class Storage(Protocol):
    async def save(self, key: str, data: BinaryIO, content_type: str) -> str: ...
    async def delete(self, key: str) -> None: ...
    def url(self, key: str) -> str: ...
```

Two implementations: `LocalStorage` (writes under `MEDIA_ROOT`) and `S3Storage`.
Selected by the `STORAGE_BACKEND` env variable. MVP runs `LocalStorage`.
No code outside `storage/` may build a filesystem path.

Local layout: `MEDIA_ROOT/properties/{property_id}/{uuid}.{ext}` with thumbnails
under `.../thumbs/{uuid}.webp`.

Technical limits (config, not business rules):
`MAX_PHOTO_MB=15`, `MAX_VIDEO_MB=200`, allowed mime types jpeg/png/webp/heic and
mp4/quicktime. The number of files per card is not limited.

Media is served by nginx from the media volume, not streamed through FastAPI.
Protect it with nginx `internal` + `X-Accel-Redirect` issued by the API so that
unauthenticated users cannot guess URLs.

Because `<img src>` cannot send a Bearer header, media URLs in API responses
carry a signed, expiring token (HMAC over media id, variant, and expiry, keyed
by `JWT_SECRET`). `GET /media/{id}/file` validates the token or a Bearer header,
checks that the media and its card are not deleted, and returns
`X-Accel-Redirect: /internal-media/<key>`. File signatures are sniffed on
upload; the client content type is not trusted. HEIC is decoded with
`pillow-heif`.

## Audit implementation

Implemented once, in `services/base.py` and `audit/`, not repeated per endpoint.

Pattern: the service loads the current row, applies the validated patch, and
diffs old versus new field by field. Each differing field produces one
`audit_log` row. Everything commits in a single transaction.

The client IP comes from a `ContextVar` set by middleware; the acting user is
set in the same context by the authentication dependency. Services still receive
the acting user explicitly because they need it for permission checks.

Login attempts are logged with `entity='user'` and `action='login'` or
`action='login_failed'`; logout with `action='logout'`.

Database triggers back the two hard invariants: `audit_log` rejects UPDATE and
DELETE, `properties` rejects DELETE.

## Authentication

Login creates a row in `auth_sessions`; access and refresh JWTs (HS256) carry
its id as `sid`. The current-user dependency loads the user and session in one
query and rejects inactive users and revoked or expired sessions. Password
hashing and verification run in a thread pool.

The login rate limiter is in-process, so the API runs one uvicorn worker.
nginx overwrites `X-Forwarded-For` with `$remote_addr`, and uvicorn trusts
proxy headers because the API port is reachable only from nginx.

## Search implementation

Search runs as one SQL query built in `repositories/properties.py`. It must not
load rows into Python to filter them. The trigram word-similarity threshold is
set per session through the connection's server settings
(`pg_trgm.word_similarity_threshold = 0.5`), so no extra statement is needed.

The `q` branches (phone, code, request number, landmark words, district,
realtor) are each index-backed, carry every filter, compute their own relevance,
and are combined with UNION ALL and grouped per card inside the same statement.
Without `q` the filtered set is an inlined CTE so the first page comes straight
from an index; with `q` it is materialized so the union runs once for both the
page and the total.

`backend/scripts/seed_benchmark.py` fills a throwaway database with 100k cards and
`backend/scripts/explain_search.py` runs `EXPLAIN ANALYZE` for typical queries.
Filters that keep most of the base (`has_media`) may use a sequential scan for the
total count: reading most rows is unavoidable there and PostgreSQL rightly prefers
the scan.

If `EXPLAIN ANALYZE` on the search query shows a sequential scan over
`properties`, the index set is wrong — fix the index, not the query shape.

## Frontend

Three screens, nothing more in MVP:

1. **Search** — sticky search input, a collapsible filter row, result table with
   thumbnails. Keyboard-first: focus lands in the search box on load, Enter
   searches, arrow keys move through results.
2. **Card** — two tabs: "Данные" (fields + media gallery) and "История"
   (audit trail). Edit in place; the save button is disabled until something
   changes.
3. **Admin** — user list, create user, reset password, toggle active; district
   list; for head/admin also the deleted-cards list and the global audit feed.

Creating a card uses the Card screen in create mode.

UI copy in Russian. No charts, no kanban, no dashboard, no notification centre.
Density over decoration: the realtor should see 15+ results without scrolling.

## Deployment

`docker-compose.yml` services: `api`, `db`, `nginx`, `backup`.
Volumes: `pgdata`, `media`; backups go to the host directory `./backups`.
The nginx image is built from `nginx/Dockerfile` and contains the frontend
bundle. The `api` container runs `alembic upgrade head` before starting uvicorn.
`TZ=Asia/Tashkent` is set in every container.
Config through `.env` only; `.env.example` is committed, `.env` is not.

Required variables:
```
DATABASE_URL, JWT_SECRET, ACCESS_TOKEN_MINUTES, REFRESH_TOKEN_DAYS,
STORAGE_BACKEND, MEDIA_ROOT, MAX_PHOTO_MB, MAX_VIDEO_MB,
CORS_ORIGINS, UZS_PER_UE=12000, TZ=Asia/Tashkent
```
Compose also reads `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, and
`HTTP_PORT`.

Backups: the `backup` service runs `pg_dump` nightly at 02:00 Tashkent time
into `./backups`, keeping 14 days.
Document the restore procedure in `README.md` — a backup nobody has restored is
not a backup.

## Security

- Argon2 password hashing, minimum password length 8, enforced server-side.
- Rate limit `/auth/login` to 10 attempts per minute per IP.
- CORS locked to the known frontend origin.
- No secrets in the repository; `JWT_SECRET` generated at install time.
- SQL exclusively through SQLAlchemy parameter binding.
- Media URLs unguessable (uuid filenames) and access-controlled.

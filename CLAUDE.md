# CLAUDE.md — Project Rules

Read `PRD.md`, `DATA_MODEL.md`, `API.md`, and `ARCHITECTURE.md` before writing
code. They are the source of truth. If something in this repository contradicts
them, the documents win — or they need updating first, which you should raise
rather than silently diverge.

## Product guardrails

This is a searchable property database, not a sales CRM. Do not add pipelines,
deal stages, kanban boards, dashboards, charts, notification centres, or
activity feeds. If a feature does not help a realtor find or edit a card,
do not build it.

## Non-negotiable technical rules

1. Properties are soft-deleted. There is no `DELETE FROM properties` anywhere.
2. Every mutation of a property writes `audit_log` rows in the same transaction.
3. Permission checks belong in `services/`. Never trust the frontend.
4. `created_by`, `updated_by`, timestamps, and `code` are set server-side and
   ignored if present in a client payload.
5. `audit_log` is append-only.
6. Filesystem paths are constructed only inside `app/storage/`.
7. Media files are served by nginx, not streamed through FastAPI handlers.
8. No raw SQL string interpolation. SQLAlchemy binding only.
9. Search must be a single SQL query. Never filter result sets in Python.

## Code conventions

- Python: ruff + black defaults, line length 100, full type hints.
- Async everywhere in the request path; no blocking IO inside handlers.
  Image processing runs in a thread pool.
- Identifiers, comments, commit messages, and docstrings in English.
  User-facing UI strings in Russian.
- Pydantic schemas are separate from ORM models. Never return an ORM object
  from a router.
- One Alembic migration per logical change, with a meaningful message.
  Never edit an applied migration; add a new one.
- Frontend: function components and hooks, TypeScript strict mode, no `any`.

## Testing

- pytest with an async client against a real PostgreSQL test database
  (testcontainers or a dedicated test DB), not SQLite — the schema uses
  PostgreSQL-specific features.
- Required coverage before a task counts as done:
  - each role's permissions on each property endpoint
  - audit rows are written with correct old and new values
  - search finds a card by phone in any input format
  - search tolerates typos in the landmark
  - soft-deleted cards never appear in search results
- Run `ruff check`, `black --check`, and `pytest` before declaring a task
  finished.

## Working style

- Build vertical slices: migration, model, repository, service, router, tests,
  UI — one feature at a time, working end to end.
- Ask before introducing a new dependency, renaming a schema field, or changing
  an API contract in `API.md`.
- Never invent business rules. If a requirement is unclear, stop and ask —
  a wrong guess here costs a migration and a data fix.
- Keep `TASKS.md` updated: tick items off as they land.

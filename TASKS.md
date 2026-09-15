# TASKS.md

Vertical slices. Each task ends with tests passing and the feature working end
to end. Do not start the next one until the current is green.

Items marked *(not run)* are written but could not be exercised on the
development machine because Docker was unavailable; they need one real
`docker compose up` before they count as done.

## Stage 0 — Foundation
- [x] 0.1 Repo skeleton per `ARCHITECTURE.md` layout; ruff, black, pytest config
- [ ] 0.2 `docker-compose.yml` with api, db, nginx; `.env.example` *(not run)*
- [x] 0.3 SQLAlchemy async engine, session dependency, settings via Pydantic
- [x] 0.4 Alembic wired up; `pg_trgm` extension migration
- [x] 0.5 `GET /health` returning db status

## Stage 1 — Users and auth
- [x] 1.1 `users` model + migration
- [x] 1.2 Argon2 hashing, JWT issue/verify, current-user dependency
- [x] 1.3 `POST /auth/login`, `/refresh`, `/logout`, `GET /auth/me`
- [x] 1.4 Role dependency helpers (`require_admin`, `require_head_or_admin`)
- [x] 1.5 CLI `create-admin`
- [x] 1.6 Login rate limiting
- [x] 1.7 Tests: login success/failure, token expiry, role guards

## Stage 2 — Audit core
- [x] 2.1 `audit_log` model + migration
- [x] 2.2 Request-context middleware (current user, IP) via ContextVar
- [x] 2.3 Generic field-diff audit helper used by all services
- [x] 2.4 Login events written to audit
- [x] 2.5 Tests: one row per changed field, old/new values correct, rollback on
      audit failure

Build this before properties. Retrofitting audit later is far more expensive.

## Stage 3 — Districts
- [x] 3.1 `districts` model + migration + seed command
- [x] 3.2 `GET/POST/PATCH /districts` with admin guard
- [x] 3.3 Tests

## Stage 4 — Property cards
- [x] 4.1 `properties` model + migration incl. generated `owner_phone_digits`
      and all indexes from `DATA_MODEL.md`
- [x] 4.2 Pydantic schemas: create, patch, list item, detail
- [x] 4.3 Service layer with permission rules (agent edits own only) + audit
- [x] 4.4 `POST /properties`, `GET /properties/{id}`, `PATCH`, `DELETE` (soft),
      `POST /{id}/restore`
- [x] 4.5 `GET /properties/{id}/history`
- [x] 4.6 Tests: full permission matrix per role, soft delete behaviour,
      server-side field overrides ignored from payload

## Stage 5 — Search
- [x] 5.1 Single-query search repository per `API.md` resolution logic
- [x] 5.2 All filters, sorting, pagination
- [x] 5.3 `EXPLAIN ANALYZE` check on 100k seeded rows; no sequential scan
      (except majority filters such as `has_media`, see `ARCHITECTURE.md`)
- [x] 5.4 Seed script generating 100k realistic rows for benchmarking
- [x] 5.5 Tests: phone in any format, typo in landmark, combined filters,
      deleted cards excluded

## Stage 6 — Media
- [x] 6.1 `property_media` model + migration
- [x] 6.2 `Storage` protocol + `LocalStorage`
- [x] 6.3 Multi-file upload, mime and size validation
- [x] 6.4 Thumbnail generation in a thread pool; video poster if ffmpeg present
- [x] 6.5 Reorder, soft-delete media
- [ ] 6.6 nginx `internal` + `X-Accel-Redirect` protected serving *(not run:
      API side tested, nginx config written, dev proxy emulation verified)*
- [x] 6.7 Tests: rejected mime, oversize file, thumbnails created, ordering

## Stage 7 — Admin API
- [x] 7.1 `GET/POST/PATCH /users`, reset password, deactivate
- [x] 7.2 `GET /audit` global feed for admin/head
- [x] 7.3 Tests

## Stage 8 — Frontend
Code is complete, type-checks in strict mode, and builds. The login screen,
routing guard, API proxy, and signed media URLs were checked in a browser;
screens behind login still need a manual pass.
- [ ] 8.1 Vite + TS + router + TanStack Query scaffold; auth flow with refresh
- [ ] 8.2 Search screen: search box, filters, dense result table, thumbnails
- [ ] 8.3 Card screen: fields, inline edit, media gallery with upload/reorder
- [ ] 8.4 History tab
- [ ] 8.5 Admin screen: users, districts
- [ ] 8.6 Mobile-usable layout pass

## Stage 9 — Operations
- [ ] 9.1 Nightly `pg_dump` backup job, 14-day retention *(not run)*
- [x] 9.2 Documented restore procedure, tested once for real (with local
      PostgreSQL 16 tools; repeat once inside Docker)
- [x] 9.3 `README.md`: install on a bare server, install on a VPS
- [x] 9.4 Structured logging, error handling, 500 page

## Stage 10 — Oversight
- [x] 10.1 `property_views` journal: card opens with 10-minute de-duplication
- [x] 10.2 `GET /views/summary`, `GET /views` for admin and head
- [x] 10.3 Audit feed names the card number and changed user or district;
      filter by card number
- [x] 10.4 Search list shows who changed a card last and when
- [x] 10.5 Tests: journaling, de-duplication, append-only, permissions, periods
- [ ] 10.6 Admin UI: «Просмотры» tab, readable «Журнал изменений»; last change in
      search and card header (type-checked and built; not clicked through)

## Later (not MVP — keep the architecture open for these)
- Sales module via `deal_type = 'sale'`
- Tenant search requests and matching against the base
- Telegram Mini App on the same API, auth via `initData`
- S3 storage backend
- Export to classified portals

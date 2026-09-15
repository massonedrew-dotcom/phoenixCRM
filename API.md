# API Contract

Base path: `/api/v1`. JSON only. No server-side rendering anywhere — the same
API will later serve a Telegram Mini App. Rationale for items marked (Dn) is in
`DECISIONS.md`.

## Conventions

- Auth: `Authorization: Bearer <access_token>`.
- Errors: `{"detail": "...", "code": "MACHINE_CODE"}` with proper HTTP status.
  `detail` is a Russian user-facing message; `code` is stable English.
- Lists: `{"items": [...], "total": 1234, "page": 1, "page_size": 50}`.
- All datetimes ISO 8601 with timezone.
- Validation errors return 422 with FastAPI's standard structure.

Common error codes: `BAD_REQUEST` and specific business codes (400),
`NOT_AUTHENTICATED` (401), `INVALID_CREDENTIALS` (401), `FORBIDDEN` (403),
`NOT_FOUND` (404), `CONFLICT` and specific codes (409), `FILE_TOO_LARGE` (413),
`UNSUPPORTED_MEDIA_TYPE` (415), `RATE_LIMITED` (429), `INTERNAL_ERROR` (500).

## Auth

```
POST   /auth/login          {username, password} -> {access_token, refresh_token, user}
POST   /auth/refresh        {refresh_token}      -> {access_token}
POST   /auth/logout         -> 204
GET    /auth/me             -> current user
POST   /auth/change-password {old_password, new_password} -> 204
```

Access token lifetime 30 minutes, refresh token 14 days. Successful and failed
logins are both written to `audit_log`, and so is logout.

Sessions are server-side (D19): `logout` revokes the current session,
`change-password` revokes all other sessions, admin password reset and
deactivation revoke all sessions of that user. A revoked session or an inactive
user makes both tokens invalid immediately.

`/auth/login` is limited to 10 attempts per minute per IP (429 `RATE_LIMITED`).

User object: `{id, username, full_name, role, is_active, created_at}`.

## Properties

```
GET    /properties
GET    /properties/deleted       head/admin only; deleted cards, newest deletion first
GET    /properties/{id}
POST   /properties
PATCH  /properties/{id}
DELETE /properties/{id}          soft delete
POST   /properties/{id}/restore  head/admin only
GET    /properties/{id}/history  audit trail for this card and its media
```

Permissions: every role creates cards and reads every active card. `agent`
updates and deletes only cards they created (403 `FORBIDDEN` otherwise);
`head` and `admin` update and delete any card. A deleted card is 404 for
`agent`; for `head`/`admin` it is readable, and PATCH/DELETE on it return 409
`PROPERTY_DELETED` until it is restored.

### GET /properties — query parameters

| param | type | meaning |
|-------|------|---------|
| `q` | string | single search box: phone digits, code, request_no, landmark, district, realtor name |
| `district_id` | uuid, repeatable | |
| `status` | hot/warm/cold, repeatable | |
| `availability` | free / occupied | derived from `occupied_until` (D3) |
| `free_from` | date | properties free on this date: `occupied_until` is null or before it |
| `created_by` | uuid, repeatable | realtor filter |
| `created_from`, `created_to` | date | date added range, inclusive, Tashkent days |
| `has_media` | bool | photos or videos |
| `sort` | created_at / updated_at / code, prefix `-` for desc | default `-created_at`; with `q` and no `sort`, relevance |
| `page`, `page_size` | int | page_size max 100, default 50 |

`q` resolution logic (D12) — a card matches if any of these match:
1. If `q` contains 5 or more digits: `owner_phone_digits LIKE '%digits%'`.
2. If `q` is a plain integer: `code = q`.
3. `request_no ILIKE '%q%'` when `q` has 3+ characters, otherwise `request_no = q`.
4. Every word of `q` with 3+ characters: `word <% landmark` — trigram word
   similarity, threshold 0.5, word order free.
5. `district.name ILIKE '%q%'` (3+ characters).
6. `users.full_name ILIKE '%q%'` of the card's creator (3+ characters).

With `q` and no explicit `sort`, results are ordered by relevance: exact
phone/code/request matches first, then `word_similarity(q, landmark)`
descending, then `created_at` descending (D13).

Deleted cards never appear in `GET /properties`.

Response items are trimmed for the list view: id, code, district name, landmark,
interest_status, free_until, occupied_until, created_by name, created_at,
cover thumbnail URL, media_count.

### POST / PATCH /properties — request body

```json
{
  "request_no": "12345",
  "district_id": "uuid",
  "landmark": "рядом с метро Чиланзар, дом 9",
  "owner_name": "Иван",
  "owner_phone": "+998 90 123-45-67",
  "interest_status": "hot",
  "free_until": "2026-10-01",
  "occupied_until": null,
  "price": "350.00",
  "note": ""
}
```

Required on POST: `district_id`, `landmark`, `owner_phone` (D2). `owner_phone`
must contain 5–15 digits. `district_id` must reference an active district,
except when PATCH leaves it unchanged (D9); otherwise 400 `DISTRICT_INACTIVE`.
Blank optional text fields are stored as null.

`price` is in у.е. (D1). There is no currency field.

Server ignores any `created_by`, `updated_by`, `created_at`, `updated_at`,
`code`, `is_deleted`, or `price_uzs` sent by the client.

PATCH is partial: only the supplied fields are changed, and only fields whose
value actually changes produce audit rows.

### Property detail response

All body fields above plus: `id`, `code`, `deal_type`, `district` `{id, name}`,
`price_uzs` (computed, `price × UZS_PER_UE`, null when price is null),
`is_deleted`, `created_by` and `updated_by` as `{id, full_name}`, `created_at`,
`updated_at`, `media` (ordered list of media records), and `can_edit` (whether
the current user may modify the card).

### History response

A list (newest first) of `{id, entity, entity_id, action, field, old_value,
new_value, user: {id, full_name} | null, ip, created_at}`, covering the card
itself and its media.

## Media

```
POST   /properties/{id}/media        multipart, field name `files`, multiple allowed
PATCH  /media/{media_id}             {sort_order}
DELETE /media/{media_id}             soft delete
GET    /media/{media_id}/file        ?variant=original|thumb; auth by Bearer or signed ?token=
```

Media records: `{id, kind, original_name, mime_type, size_bytes, sort_order,
uploaded_at, url, thumb_url}`. `url` and `thumb_url` are signed and valid for
12 hours (D22).

Upload, reorder, and delete follow the card's edit permission. Upload response
returns the created media records with their URLs. Thumbnails are generated
synchronously for photos on upload; video files get a poster frame extracted if
ffmpeg is available, otherwise `thumb_key` stays null.

Rejected files: 415 `UNSUPPORTED_MEDIA_TYPE` (by file signature), 413
`FILE_TOO_LARGE`. One rejected file rejects the whole upload.

`GET /media/{id}/file` never streams bytes itself: it answers with
`X-Accel-Redirect` to an nginx `internal` location.

## Users (admin only, except `GET /users` which `head` may also call)

```
GET    /users
POST   /users                   {username, full_name, password, role}
PATCH  /users/{id}              {full_name, role, is_active}
POST   /users/{id}/reset-password {new_password}
```

Passwords are never returned by any endpoint. Minimum length 8. Usernames are
stored lowercase. An admin cannot deactivate themselves or change their own
role (D11).

## Realtors

```
GET    /realtors                any authenticated user -> [{id, full_name, is_active}]
```

## Districts

```
GET    /districts               any authenticated user; includes inactive
POST   /districts               admin  {name}
PATCH  /districts/{id}          admin  {name, is_active}
```

## Audit

```
GET /audit?entity=&entity_id=&user_id=&action=&date_from=&date_to=&page=&page_size=
```

Admin and head see everything. Agents may read history of any single property
through `/properties/{id}/history` but cannot query the global audit feed.

## Client config

```
GET /config   any authenticated user -> {uzs_per_ue, max_photo_mb, max_video_mb, time_zone}
```

Lets the card form show the сум amount while the price is typed, and warn about
file size limits before an upload.

## Health

```
GET /health -> {"status": "ok", "db": "ok"}
```

Full path `/api/v1/health`, no auth. When the database is unreachable it returns
`503 {"status": "error", "db": "error"}`.

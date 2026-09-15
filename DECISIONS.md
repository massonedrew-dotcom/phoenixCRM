# Decisions

Answers to gaps and contradictions found in the original documents. The
product owner delegated these choices ("decide the architecture yourself"),
except D1, which is a direct business instruction. Each decision is already
folded into `PRD.md`, `DATA_MODEL.md`, `API.md`, or `ARCHITECTURE.md`; this file
records why.

## Business

**D1. Price is in у.е., converted to сум automatically.** `properties.price` is
entered and stored in у.е. (conventional units). The сум amount is never stored:
it is computed on read as `price × UZS_PER_UE` (currently 12 000, a config
value). The `currency` column is removed.

**D2. Required card fields** are `district_id`, `landmark`, and `owner_phone`
(the database schema was more specific than the PRD). `owner_phone` must contain
5 to 15 digits; `+`, spaces, `-`, `(`, `)` are allowed as separators.

**D3. Availability** is derived from `occupied_until` only:
- occupied: `occupied_until >= today`
- free: `occupied_until IS NULL OR occupied_until < today`
- `free_from = D` (free on date D): `occupied_until IS NULL OR occupied_until < D`

`free_until` is informational (shown on the card and in the list) and does not
take part in the availability filter.

**D4. "Today" and date ranges use Asia/Tashkent.** `created_from`/`created_to`
cover whole Tashkent days; "today" in the availability filter is the Tashkent
date. Timestamps are still stored as `timestamptz`.

**D5. History is readable by every authenticated user** (PRD §8 and API.md
agree; the role table in PRD §3 only lists it for `head` as an example).

**D6. Deleted cards.** Search never returns them. `head` and `admin` see them
through a separate list `GET /properties/deleted` and can open and restore them.
For `agent` a deleted card is 404.

**D7. Media of a deleted card.** Deleting a card does not modify its media rows;
media of a deleted card are hidden and inaccessible because the card is.
Restoring a card brings back exactly the media that were visible before.
Media deleted individually stay deleted.

**D8. Cover and `has_media`.** The cover is the first photo by `sort_order`;
if a card has no photos, the first video poster is used. `has_media` counts
photos and videos.

**D9. District references.** `GET /districts` returns all districts including
inactive ones (needed to render old cards and filters). A card cannot be created
with, or moved to, an inactive district; a card already in a district that was
later deactivated can still be edited.

**D10. Realtor list for everyone.** `GET /realtors` returns `id`, `full_name`,
`is_active` of all users to any authenticated user, so agents can use the
realtor filter. `GET /users` stays admin/head only.

**D11. Admin self-protection.** An admin cannot deactivate their own account or
change their own role.

## Search

**D12. `q` resolution.** Matches are the union of:
1. phone: if `q` has ≥5 digits, `owner_phone_digits LIKE '%digits%'`
2. code: if `q` is a plain integer, `code = q`
3. request number: `request_no ILIKE '%q%'` if `q` has ≥3 characters, otherwise
   `request_no = q`
4. landmark: every word of `q` with 3+ characters satisfies `word <% landmark`
   (trigram *word* similarity, threshold 0.5). This tolerates typos and word order
   and finds a short word inside a long text. Plain `similarity()` from the original
   API.md could not find "метро" in "рядом с метро Чиланзар, дом 9".
5. district name `ILIKE '%q%'`
6. realtor full name `ILIKE '%q%'`

Branches 4–6 run only when `q` has 3+ characters: one or two characters carry no
trigram signal and would match most of the base. LIKE wildcards in `q` are
escaped. Each branch is indexable and carries all filters; the branches are
combined with UNION in one SQL statement.

Why per word: comparing the whole query at 0.5 let "метро Ойбек" match every
landmark containing "метро", and raising the threshold to 0.6 lost real typos
("Чилнзар" scores 0.55 against "Чиланзар"). Single words separate cleanly:
typos score 0.54–0.75, unrelated words 0. A multi-word query is not split across
fields: "Чиланзар 9 квартал" does not combine a district with a landmark.

Measured on 100k generated cards (local PostgreSQL 16 on Windows): typical queries
1–120 ms; a very common single word ("дом", in 20% of landmarks) 270–340 ms,
which is at the 300 ms target.

**D13. Ordering with `q`.** Without an explicit `sort`, results with `q` are
ordered by relevance: exact phone/code/request matches first, then by
`word_similarity(q, landmark)`, then `created_at DESC`. An explicit `sort` wins.
Each branch computes its own relevance and the best one per card is kept, so
trigram similarity is evaluated once per row.

## Audit

**D14. Create writes one row per populated field** (`old_value = NULL`).
Delete and restore write one row with `field = NULL`.

**D15. What is audited.** Entities: `property`, `media`, `user`, `district`.
Password changes and resets are audited as `update` of field `password` with
both values `NULL` — hashes are never written to the log.

**D16. Login events.** Actions `login`, `login_failed`, `logout`.
`audit_log.user_id` and `entity_id` are nullable: a failed login has
`user_id = NULL`, `entity_id` = the matched user or `NULL` if the username does
not exist, `field = 'username'`, `new_value` = the attempted username.
Districts added by `python -m app.cli seed-districts` are audited with
`user_id = NULL` because no user performs them.

**D17. Media changes do not touch the property row.** Uploads, reorders, and
deletions are audited as entity `media`; the card history endpoint includes
them (joined through `property_media.property_id`). `properties.updated_at` is
not changed by media operations.

**D18. Append-only and soft delete are enforced by the database too.** Triggers
reject `UPDATE`/`DELETE` on `audit_log` and `DELETE` on `properties`.

## Auth

**D19. Server-side sessions.** Login creates an `auth_sessions` row; access and
refresh JWTs carry its id (`sid`). Every authenticated request checks that the
session is not revoked and the user is active — deactivation takes effect
immediately. `logout` revokes the current session; `change-password` revokes
all other sessions of the user; `reset-password` and deactivation revoke all of
them. Refresh does not rotate the refresh token (the API returns only
`access_token`).

**D20. Login rate limit** is in-process (sliding window, 10 attempts per minute
per IP), so the API runs a single uvicorn worker. The client IP comes from
nginx, which overwrites `X-Forwarded-For` with `$remote_addr`.

**D21. Frontend token storage.** Access token in memory, refresh token in
`localStorage`. The same Bearer flow will serve the Telegram Mini App.

## Media and infrastructure

**D22. Media URLs are signed.** `<img src>` cannot send an `Authorization`
header, so media URLs in API responses carry a short-lived HMAC token
(`?token=`, valid 12 hours). `GET /media/{id}/file` accepts either that token or
a Bearer token, checks access, and answers with `X-Accel-Redirect`; nginx serves
the bytes from an `internal` location. An S3 backend will answer with a
redirect to a presigned URL instead.

**D23. Upload validation** sniffs file signatures; the client-supplied content
type is not trusted. HEIC is decoded with `pillow-heif`. Thumbnails are 480 px
WebP. ffmpeg is installed in the API image for video posters, and its absence
is tolerated.

**D24. Deployment.** Compose services: `db`, `api`, `nginx`, `backup`. The
nginx image is built with the frontend bundle. Migrations run when the `api`
container starts. `TZ=Asia/Tashkent` is set in every container.

**D25. Tests** use testcontainers when Docker is available, otherwise a
dedicated local PostgreSQL server (`TEST_DATABASE_ADMIN_URL`). Either way each
test session creates a fresh database, and each test runs inside a transaction
that is rolled back.

**D26. Health endpoint.** `GET /api/v1/health`; `503 {"status":"error","db":"error"}`
when the database is unreachable.

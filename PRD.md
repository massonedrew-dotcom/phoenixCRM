# PRD — Rental Property Database CRM

## 1. Context

A real estate agency currently uses a local system called "Luzia". It is slow to
search, cluttered, and provides no reliable change history. This project replaces
it with a focused internal web application.

## 2. What this product IS and IS NOT

**IS:** a well-structured, searchable database of rental properties with photos,
videos, and a complete audit trail of every change.

**IS NOT:** a sales funnel, a pipeline board, a lead-scoring engine, or a
dashboard product. Do not add kanban boards, deal stages, charts, or gamification.
Every UI element must serve either *finding a property* or *editing a property*.

Design rule: if a button does not help a realtor find or update a card, it does
not belong in the interface.

## 3. Users and roles

| Role  | Capabilities |
|-------|--------------|
| admin | Creates/deactivates users, sets logins and passwords, assigns roles, views full audit log. Has all `head` capabilities. |
| head  | Head of department. Sees and edits every card. Restores deleted cards. Views the global audit log. |
| agent | Realtor. Sees every card including the owner's phone number. Creates new cards. Edits and deletes only their own cards. Other agents' cards are read-only. |

Notes:
- Self-registration does not exist. Only `admin` creates accounts.
- Owner phone numbers are visible to all authenticated users. This is a
  deliberate business decision, not an oversight.

## 4. Scope — MVP

In scope:
1. Login with username and password; session via JWT.
2. Rental property cards: create, view, edit, soft-delete.
3. Photo and video upload per card, with thumbnails and ordering.
4. Search and filtering (see section 5) — the core feature.
5. Audit log of every field change on every card, with viewer UI.
6. Admin panel for user management.

Out of scope for MVP (planned later, must not be blocked by architecture):
- Sales department module (apartment sales) — a separate property type reusing
  the same entities.
- Tenant/client search requests and matching.
- Telegram Mini App — will consume the same JSON API, no server-side rendering.
- Listing export to classified portals.
- Telephony integration.

## 5. Search — the central feature

The main screen is a search field plus filters and a result list. No dashboard.

**Single search box** queries across, simultaneously:
- owner phone number (digits-only matching, so any input format works)
- card number (`code`)
- request number (`request_no`)
- landmark text (`landmark`) — fuzzy, tolerant of typos and word order
- district name
- realtor name (the person who created the card)

**Filters** (combinable, applied on top of the search box):
- district (multi-select)
- interest status: hot / warm / cold
- availability: currently free / occupied / free on a given date
  (derived from `occupied_until`)
- realtor (who created the card)
- date added (range)
- has media / no media

**Result list** shows: thumbnail, district, landmark, status badge, free-until /
occupied-until, realtor name, date added. Sorted by date added descending by
default. Pagination or infinite scroll, 50 per page.

Performance target: search returns in under 300 ms on 100,000 cards.

## 6. Property card fields

Auto-filled by the system (never editable by hand):
- internal ID
- created_by, created_at
- updated_by, updated_at

Entered by the realtor:
- `request_no` — the agency's real estate request number
- `district` — reference list, managed by admin
- `landmark` — free text (e.g. nearest metro, building, crossroads)
- `owner_phone` — required
- `owner_name` — optional
- `interest_status` — hot / warm / cold, set manually
- `free_until` — date, nullable
- `occupied_until` — date, nullable
- `price` — optional, entered in у.е. (conventional units). The amount in сум is
  calculated automatically at a fixed rate of 12 000 сум per 1 у.е. (a
  configuration value) and shown next to it; it is never typed in.
- `note` — free text

Required: `district`, `landmark`, `owner_phone`.

## 7. Media

- Multiple photos and multiple videos per card. No hard business limit; enforce
  only technical limits (see ARCHITECTURE.md).
- Photos get generated thumbnails; lists must never load full-size images.
- Media ordering is user-controlled; the first photo is the cover.
- Deleting a card hides its media too; files stay on disk. Restoring the card
  brings its media back.

## 8. Audit requirements

Every create, update, soft-delete, and restore of a property card, and every
media upload, reorder, and removal, is recorded with: who, when, which field,
previous value, new value, and client IP. Changes to users and districts and
login attempts are recorded too.

Cards are never hard-deleted — that would destroy the audit trail.
The card view has a "History" tab showing the change log in reverse
chronological order, readable by every authenticated user.

## 9. Non-functional requirements

- UI language: Russian. Code, identifiers, and comments: English.
- Deployment must be identical locally, on the agency's own server, and on a VPS.
- File storage must be swappable from local disk to S3 via configuration only.
- Works on desktop browsers primarily; layout must remain usable on a phone.
- Daily automated database backup.

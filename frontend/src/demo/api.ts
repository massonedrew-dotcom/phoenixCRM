/** In-browser stand-in for the API, used by the GitHub Pages demo build.
 *
 * It mirrors the rules of the real server — role permissions, soft delete, the audit
 * log, and the view journal — over data kept in localStorage. It is a demonstration,
 * not a security boundary: there is no password check, because there is no server. */
import { ApiError, type RequestOptions } from "../api/client";
import type {
  AuditAction,
  AuditEntry,
  District,
  InterestStatus,
  Media,
  Page,
  Property,
  PropertyFields,
  PropertyListItem,
  Role,
  User,
  UserViewSummary,
  ViewEntry,
} from "../api/types";
import { DEMO_IP, type DemoAudit, type DemoMedia, type DemoProperty } from "./seed";
import { demoState, saveDemoState } from "./store";

const UZS_PER_UE = "12000";
const REPEAT_VIEW_MINUTES = 10;
const DEFAULT_PAGE_SIZE = 50;

type Query = URLSearchParams;

function notFound(message = "Не найдено"): ApiError {
  return new ApiError(404, "NOT_FOUND", message);
}

function forbidden(message = "Недостаточно прав"): ApiError {
  return new ApiError(403, "FORBIDDEN", message);
}

function currentUser(): User {
  const state = demoState();
  const user = state.users.find((candidate) => candidate.id === state.current_user_id);
  if (user === undefined) {
    throw new ApiError(401, "NOT_AUTHENTICATED", "Требуется вход в систему");
  }
  return user;
}

function isManager(user: User): boolean {
  return user.role === "admin" || user.role === "head";
}

function requireManager(user: User): void {
  if (!isManager(user)) throw forbidden();
}

function nowIso(): string {
  return new Date().toISOString();
}

function userRef(id: string | null): { id: string; full_name: string } | null {
  if (id === null) return null;
  const user = demoState().users.find((candidate) => candidate.id === id);
  return user ? { id: user.id, full_name: user.full_name } : null;
}

function districtName(id: string): string {
  return demoState().districts.find((district) => district.id === id)?.name ?? "—";
}

function activeMedia(propertyId: string): DemoMedia[] {
  return demoState()
    .media.filter((item) => item.property_id === propertyId && !item.is_deleted)
    .sort((a, b) => a.sort_order - b.sort_order || a.uploaded_at.localeCompare(b.uploaded_at));
}

function toMedia(item: DemoMedia): Media {
  return {
    id: item.id,
    kind: item.kind,
    original_name: item.original_name,
    mime_type: item.mime_type,
    size_bytes: item.size_bytes,
    sort_order: item.sort_order,
    uploaded_at: item.uploaded_at,
    url: item.url,
    thumb_url: item.thumb_url,
  };
}

function canEdit(user: User, property: DemoProperty): boolean {
  return isManager(user) || property.created_by === user.id;
}

function priceUzs(price: string | null): string | null {
  if (price === null) return null;
  return (Number(price) * Number(UZS_PER_UE)).toFixed(2);
}

function toDetail(property: DemoProperty, user: User): Property {
  return {
    id: property.id,
    code: property.code,
    deal_type: "rent",
    request_no: property.request_no,
    district: { id: property.district_id, name: districtName(property.district_id) },
    landmark: property.landmark,
    owner_name: property.owner_name,
    owner_phone: property.owner_phone,
    interest_status: property.interest_status,
    free_until: property.free_until,
    occupied_until: property.occupied_until,
    price: property.price,
    price_uzs: priceUzs(property.price),
    note: property.note,
    is_deleted: property.is_deleted,
    created_by: userRef(property.created_by) ?? { id: property.created_by, full_name: "—" },
    created_at: property.created_at,
    updated_by: userRef(property.updated_by),
    updated_at: property.updated_at,
    media: property.is_deleted ? [] : activeMedia(property.id).map(toMedia),
    can_edit: !property.is_deleted && canEdit(user, property),
  };
}

function toListItem(property: DemoProperty): PropertyListItem {
  const cover = activeMedia(property.id).find((item) => item.thumb_url !== null);
  return {
    id: property.id,
    code: property.code,
    district_name: districtName(property.district_id),
    landmark: property.landmark,
    interest_status: property.interest_status,
    free_until: property.free_until,
    occupied_until: property.occupied_until,
    created_by_name: userRef(property.created_by)?.full_name ?? "—",
    created_at: property.created_at,
    updated_by_name: userRef(property.updated_by)?.full_name ?? null,
    updated_at: property.updated_at,
    cover_thumb_url: cover?.thumb_url ?? null,
    media_count: activeMedia(property.id).length,
  };
}

function writeAudit(row: Omit<DemoAudit, "id" | "ip" | "created_at">): void {
  const state = demoState();
  state.audit.push({ ...row, id: state.next_audit_id++, ip: DEMO_IP, created_at: nowIso() });
}

function toAuditEntry(row: DemoAudit, withSubject: boolean): AuditEntry {
  const state = demoState();
  const entry: AuditEntry = {
    id: row.id,
    entity: row.entity,
    entity_id: row.entity_id,
    action: row.action,
    field: row.field,
    old_value: row.old_value,
    new_value: row.new_value,
    user: userRef(row.user_id),
    ip: row.ip,
    created_at: row.created_at,
  };
  if (!withSubject) return entry;

  let property: DemoProperty | undefined;
  if (row.entity === "property") {
    property = state.properties.find((item) => item.id === row.entity_id);
  } else if (row.entity === "media") {
    const media = state.media.find((item) => item.id === row.entity_id);
    property = state.properties.find((item) => item.id === media?.property_id);
  }
  return {
    ...entry,
    property_id: property?.id ?? null,
    property_code: property?.code ?? null,
    subject_name:
      row.entity === "user"
        ? (userRef(row.entity_id)?.full_name ?? null)
        : row.entity === "district"
          ? (state.districts.find((item) => item.id === row.entity_id)?.name ?? null)
          : null,
  };
}

/** Same spirit as the server: digits for phones, words for landmarks, typos tolerated. */
function distance(a: string, b: string): number {
  const rows = Array.from({ length: b.length + 1 }, (_, index) => index);
  for (let i = 1; i <= a.length; i += 1) {
    let previous = rows[0] as number;
    rows[0] = i;
    for (let j = 1; j <= b.length; j += 1) {
      const current = rows[j] as number;
      rows[j] = Math.min(
        current + 1,
        (rows[j - 1] as number) + 1,
        previous + (a[i - 1] === b[j - 1] ? 0 : 1),
      );
      previous = current;
    }
  }
  return rows[b.length] as number;
}

function wordMatches(word: string, text: string): boolean {
  if (text.includes(word)) return true;
  const allowed = word.length >= 6 ? 2 : 1;
  return text
    .split(/[^\p{L}\p{N}]+/u)
    .some((candidate) => candidate.length >= 3 && distance(word, candidate) <= allowed);
}

function matchesQuery(property: DemoProperty, raw: string): boolean {
  const query = raw.trim().toLowerCase();
  if (query === "") return true;
  const digits = query.replace(/\D/g, "");
  const phoneDigits = property.owner_phone.replace(/\D/g, "");
  if (digits.length >= 5 && phoneDigits.includes(digits)) return true;
  if (/^\d+$/.test(query) && property.code === Number(query)) return true;
  const requestNo = (property.request_no ?? "").toLowerCase();
  if (requestNo !== "" && (query.length >= 3 ? requestNo.includes(query) : requestNo === query)) {
    return true;
  }
  if (query.length < 3) return false;
  if (districtName(property.district_id).toLowerCase().includes(query)) return true;
  if ((userRef(property.created_by)?.full_name ?? "").toLowerCase().includes(query)) return true;
  const landmark = property.landmark.toLowerCase();
  const words = query.split(/[^\p{L}\p{N}]+/u).filter((word) => word.length >= 3);
  return words.length > 0 && words.every((word) => wordMatches(word, landmark));
}

function todayIso(): string {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Tashkent",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date());
}

function withinDates(value: string, from: string | null, to: string | null): boolean {
  const day = value.slice(0, 10);
  if (from !== null && day < from) return false;
  return !(to !== null && day > to);
}

function paginate<T>(items: T[], query: Query, defaultSize = DEFAULT_PAGE_SIZE): Page<T> {
  const page = Number(query.get("page") ?? 1) || 1;
  const pageSize = Number(query.get("page_size") ?? defaultSize) || defaultSize;
  const start = (page - 1) * pageSize;
  return { items: items.slice(start, start + pageSize), total: items.length, page, page_size: pageSize };
}

function searchProperties(query: Query): Page<PropertyListItem> {
  const state = demoState();
  const today = todayIso();
  const districts = query.getAll("district_id");
  const statuses = query.getAll("status") as InterestStatus[];
  const creators = query.getAll("created_by");
  const availability = query.get("availability");
  const freeFrom = query.get("free_from");
  const hasMedia = query.get("has_media");
  const q = query.get("q") ?? "";

  let found = state.properties.filter((property) => {
    if (property.is_deleted) return false;
    if (districts.length > 0 && !districts.includes(property.district_id)) return false;
    if (statuses.length > 0 && !statuses.includes(property.interest_status)) return false;
    if (creators.length > 0 && !creators.includes(property.created_by)) return false;
    const occupiedNow = property.occupied_until !== null && property.occupied_until >= today;
    if (availability === "occupied" && !occupiedNow) return false;
    if (availability === "free" && occupiedNow) return false;
    if (freeFrom !== null && property.occupied_until !== null && property.occupied_until >= freeFrom) {
      return false;
    }
    if (!withinDates(property.created_at, query.get("created_from"), query.get("created_to"))) {
      return false;
    }
    const mediaCount = activeMedia(property.id).length;
    if (hasMedia === "true" && mediaCount === 0) return false;
    if (hasMedia === "false" && mediaCount > 0) return false;
    return matchesQuery(property, q);
  });

  const sort = query.get("sort");
  const changed = (property: DemoProperty) => property.updated_at ?? property.created_at;
  const comparators: Record<string, (a: DemoProperty, b: DemoProperty) => number> = {
    created_at: (a, b) => a.created_at.localeCompare(b.created_at),
    "-created_at": (a, b) => b.created_at.localeCompare(a.created_at),
    updated_at: (a, b) => changed(a).localeCompare(changed(b)),
    "-updated_at": (a, b) => changed(b).localeCompare(changed(a)),
    code: (a, b) => a.code - b.code,
    "-code": (a, b) => b.code - a.code,
  };
  found = [...found].sort(comparators[sort ?? "-created_at"] ?? comparators["-created_at"]!);

  const page = paginate(found, query);
  return { ...page, items: page.items.map(toListItem) };
}

function recordView(property: DemoProperty, user: User): void {
  const state = demoState();
  const since = new Date(Date.now() - REPEAT_VIEW_MINUTES * 60_000).toISOString();
  const recent = state.views.some(
    (view) =>
      view.property_id === property.id && view.user_id === user.id && view.viewed_at > since,
  );
  if (recent) return;
  state.views.push({
    id: state.next_view_id++,
    property_id: property.id,
    user_id: user.id,
    viewed_at: nowIso(),
    ip: DEMO_IP,
  });
}

function findProperty(id: string): DemoProperty {
  const property = demoState().properties.find((item) => item.id === id);
  if (property === undefined) throw notFound("Карточка не найдена");
  return property;
}

function applyPatch(property: DemoProperty, patch: Partial<PropertyFields>, user: User): void {
  const changes: [string, string | null, string | null][] = [];
  for (const [field, value] of Object.entries(patch) as [keyof PropertyFields, unknown][]) {
    const before = property[field] as string | null;
    const after = (value ?? null) as string | null;
    const same = field === "price" ? Number(before ?? NaN) === Number(after ?? NaN) : before === after;
    if (same && !(before === null && after === null)) continue;
    if (before === after) continue;
    changes.push([field, before, after]);
    Object.assign(property, { [field]: after });
  }
  if (changes.length === 0) return;
  property.updated_by = user.id;
  property.updated_at = nowIso();
  for (const [field, oldValue, newValue] of changes) {
    writeAudit({
      entity: "property",
      entity_id: property.id,
      action: "update",
      field,
      old_value: oldValue,
      new_value: newValue,
      user_id: user.id,
    });
  }
}

function viewSummary(query: Query): UserViewSummary[] {
  const state = demoState();
  const from = query.get("date_from");
  const to = query.get("date_to");
  const perUser = new Map<string, { views: number; cards: Set<string>; last: string }>();
  for (const view of state.views) {
    if (!withinDates(view.viewed_at, from, to)) continue;
    const entry = perUser.get(view.user_id) ?? { views: 0, cards: new Set<string>(), last: "" };
    entry.views += 1;
    entry.cards.add(view.property_id);
    entry.last = entry.last > view.viewed_at ? entry.last : view.viewed_at;
    perUser.set(view.user_id, entry);
  }
  return [...perUser.entries()]
    .map(([userId, entry]) => {
      const user = state.users.find((candidate) => candidate.id === userId);
      return {
        user_id: userId,
        full_name: user?.full_name ?? "—",
        username: user?.username ?? "—",
        role: (user?.role ?? "agent") as Role,
        is_active: user?.is_active ?? true,
        views: entry.views,
        cards: entry.cards.size,
        last_viewed_at: entry.last,
      };
    })
    .sort((a, b) => b.cards - a.cards || a.full_name.localeCompare(b.full_name));
}

function listViews(query: Query): Page<ViewEntry> {
  const state = demoState();
  const userId = query.get("user_id");
  const code = query.get("property_code");
  const rows = state.views
    .filter((view) => {
      if (!withinDates(view.viewed_at, query.get("date_from"), query.get("date_to"))) return false;
      if (userId !== null && view.user_id !== userId) return false;
      if (code !== null) {
        const property = state.properties.find((item) => item.id === view.property_id);
        if (property?.code !== Number(code)) return false;
      }
      return true;
    })
    .sort((a, b) => b.viewed_at.localeCompare(a.viewed_at));
  const page = paginate(rows, query);
  return {
    ...page,
    items: page.items.map((view) => {
      const property = state.properties.find((item) => item.id === view.property_id);
      return {
        id: view.id,
        viewed_at: view.viewed_at,
        user: userRef(view.user_id) ?? { id: view.user_id, full_name: "—" },
        property: {
          id: view.property_id,
          code: property?.code ?? 0,
          landmark: property?.landmark ?? "—",
        },
        ip: view.ip,
      };
    }),
  };
}

function auditFeed(query: Query): Page<AuditEntry> {
  const state = demoState();
  const entity = query.get("entity");
  const action = query.get("action") as AuditAction | null;
  const userId = query.get("user_id");
  const code = query.get("property_code");
  const rows = state.audit
    .filter((row) => {
      if (entity !== null && row.entity !== entity) return false;
      if (action !== null && row.action !== action) return false;
      if (userId !== null && row.user_id !== userId) return false;
      if (!withinDates(row.created_at, query.get("date_from"), query.get("date_to"))) return false;
      if (code !== null) {
        const entry = toAuditEntry(row, true);
        if (entry.property_code !== Number(code)) return false;
      }
      return true;
    })
    .sort((a, b) => b.created_at.localeCompare(a.created_at) || b.id - a.id);
  const page = paginate(rows, query);
  return { ...page, items: page.items.map((row) => toAuditEntry(row, true)) };
}

function propertyHistory(propertyId: string): AuditEntry[] {
  const state = demoState();
  const mediaIds = new Set(
    state.media.filter((item) => item.property_id === propertyId).map((item) => item.id),
  );
  return state.audit
    .filter(
      (row) =>
        (row.entity === "property" && row.entity_id === propertyId) ||
        (row.entity === "media" && row.entity_id !== null && mediaIds.has(row.entity_id)),
    )
    .sort((a, b) => b.created_at.localeCompare(a.created_at) || b.id - a.id)
    .map((row) => toAuditEntry(row, false));
}

function login(body: { username: string }): unknown {
  const state = demoState();
  const username = body.username.trim().toLowerCase();
  const user = state.users.find((candidate) => candidate.username === username);
  if (user === undefined || !user.is_active) {
    throw new ApiError(401, "INVALID_CREDENTIALS", "В демо доступны логины: admin, head, dilnoza, rustam");
  }
  state.current_user_id = user.id;
  writeAudit({
    entity: "user",
    entity_id: user.id,
    action: "login",
    field: null,
    old_value: null,
    new_value: null,
    user_id: user.id,
  });
  return { access_token: "demo", refresh_token: "demo", token_type: "bearer", user };
}

function createProperty(fields: PropertyFields, user: User): Property {
  const state = demoState();
  const district = state.districts.find((item) => item.id === fields.district_id);
  if (district === undefined || !district.is_active) {
    throw new ApiError(400, "DISTRICT_INACTIVE", "Район отключён, выберите другой");
  }
  const property: DemoProperty = {
    ...fields,
    id: `property-${Date.now()}`,
    code: ++state.next_code,
    is_deleted: false,
    created_by: user.id,
    created_at: nowIso(),
    updated_by: null,
    updated_at: null,
  };
  state.properties.push(property);
  for (const [field, value] of Object.entries(fields)) {
    if (value !== null && value !== undefined) {
      writeAudit({
        entity: "property",
        entity_id: property.id,
        action: "create",
        field,
        old_value: null,
        new_value: String(value),
        user_id: user.id,
      });
    }
  }
  return toDetail(property, user);
}

async function uploadMedia(propertyId: string, form: FormData, user: User): Promise<Media[]> {
  const property = findProperty(propertyId);
  if (property.is_deleted) throw notFound("Карточка не найдена");
  if (!canEdit(user, property)) throw forbidden("Можно изменять только свои карточки");
  const state = demoState();
  const files = form.getAll("files").filter((item): item is File => item instanceof File);
  const created: DemoMedia[] = [];
  let order = activeMedia(propertyId).reduce((max, item) => Math.max(max, item.sort_order + 1), 0);
  for (const file of files) {
    if (!file.type.startsWith("image/")) {
      throw new ApiError(415, "UNSUPPORTED_MEDIA_TYPE", "В демо можно загружать только фотографии");
    }
    const dataUrl = await new Promise<string>((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result));
      reader.onerror = () => reject(new ApiError(0, "READ_ERROR", "Не удалось прочитать файл"));
      reader.readAsDataURL(file);
    });
    const media: DemoMedia = {
      id: `media-${Date.now()}-${order}`,
      property_id: propertyId,
      kind: "photo",
      original_name: file.name,
      mime_type: file.type,
      size_bytes: file.size,
      sort_order: order++,
      is_deleted: false,
      uploaded_by: user.id,
      uploaded_at: nowIso(),
      url: dataUrl,
      thumb_url: dataUrl,
    };
    state.media.push(media);
    created.push(media);
    writeAudit({
      entity: "media",
      entity_id: media.id,
      action: "create",
      field: "original_name",
      old_value: null,
      new_value: media.original_name,
      user_id: user.id,
    });
  }
  saveDemoState();
  return created.map(toMedia);
}

function findMedia(mediaId: string, user: User): DemoMedia {
  const media = demoState().media.find((item) => item.id === mediaId);
  if (media === undefined || media.is_deleted) throw notFound("Файл не найден");
  const property = findProperty(media.property_id);
  if (property.is_deleted) throw notFound("Файл не найден");
  if (!canEdit(user, property)) throw forbidden("Можно изменять только свои карточки");
  return media;
}

// eslint-disable-next-line complexity -- one switchboard is clearer than many tiny routers
function route(method: string, path: string, query: Query, body: unknown): unknown {
  const state = demoState();
  if (path === "/auth/login" && method === "POST") return login(body as { username: string });
  if (path === "/auth/refresh" && method === "POST") {
    if (state.current_user_id === null) throw new ApiError(401, "NOT_AUTHENTICATED", "Сессия истекла");
    return { access_token: "demo", token_type: "bearer" };
  }
  if (path === "/auth/logout") {
    state.current_user_id = null;
    return undefined;
  }

  const user = currentUser();

  if (path === "/auth/me") return user;
  if (path === "/auth/change-password") return undefined;
  if (path === "/config") {
    return { uzs_per_ue: UZS_PER_UE, max_photo_mb: 15, max_video_mb: 200, time_zone: "Asia/Tashkent" };
  }
  if (path === "/districts" && method === "GET") {
    return [...state.districts].sort((a, b) => a.name.localeCompare(b.name));
  }
  if (path === "/realtors") {
    return state.users.map((item) => ({
      id: item.id,
      full_name: item.full_name,
      is_active: item.is_active,
    }));
  }
  if (path === "/users" && method === "GET") {
    requireManager(user);
    return [...state.users].sort((a, b) => a.full_name.localeCompare(b.full_name));
  }
  if (path === "/properties" && method === "GET") return searchProperties(query);
  if (path === "/properties" && method === "POST") {
    return createProperty(body as PropertyFields, user);
  }
  if (path === "/properties/deleted") {
    requireManager(user);
    const rows = state.properties
      .filter((property) => property.is_deleted)
      .sort((a, b) => (b.updated_at ?? "").localeCompare(a.updated_at ?? ""))
      .map((property) => ({
        id: property.id,
        code: property.code,
        district_name: districtName(property.district_id),
        landmark: property.landmark,
        created_by_name: userRef(property.created_by)?.full_name ?? "—",
        deleted_by_name: userRef(property.updated_by)?.full_name ?? null,
        deleted_at: property.updated_at,
      }));
    return paginate(rows, query);
  }
  if (path === "/views/summary") {
    requireManager(user);
    return viewSummary(query);
  }
  if (path === "/views") {
    requireManager(user);
    return listViews(query);
  }
  if (path === "/audit") {
    requireManager(user);
    return auditFeed(query);
  }

  const propertyMatch = /^\/properties\/([^/]+)(\/[a-z]+)?$/.exec(path);
  if (propertyMatch) {
    const property = findProperty(propertyMatch[1] as string);
    const suffix = propertyMatch[2];
    const visible = !property.is_deleted || isManager(user);
    if (!visible) throw notFound("Карточка не найдена");

    if (suffix === "/history" && method === "GET") return propertyHistory(property.id);
    if (suffix === "/media" && method === "POST") throw notFound();
    if (suffix === "/restore" && method === "POST") {
      requireManager(user);
      if (!property.is_deleted) throw new ApiError(409, "PROPERTY_NOT_DELETED", "Карточка не удалена");
      property.is_deleted = false;
      property.updated_by = user.id;
      property.updated_at = nowIso();
      writeAudit({
        entity: "property",
        entity_id: property.id,
        action: "restore",
        field: null,
        old_value: null,
        new_value: null,
        user_id: user.id,
      });
      return toDetail(property, user);
    }
    if (suffix === undefined && method === "GET") {
      recordView(property, user);
      return toDetail(property, user);
    }
    if (suffix === undefined && method === "PATCH") {
      if (property.is_deleted) {
        throw new ApiError(409, "PROPERTY_DELETED", "Карточка удалена. Сначала восстановите её");
      }
      if (!canEdit(user, property)) throw forbidden("Можно изменять только свои карточки");
      applyPatch(property, body as Partial<PropertyFields>, user);
      return toDetail(property, user);
    }
    if (suffix === undefined && method === "DELETE") {
      if (property.is_deleted) throw new ApiError(409, "PROPERTY_DELETED", "Карточка уже удалена");
      if (!canEdit(user, property)) throw forbidden("Можно изменять только свои карточки");
      property.is_deleted = true;
      property.updated_by = user.id;
      property.updated_at = nowIso();
      writeAudit({
        entity: "property",
        entity_id: property.id,
        action: "delete",
        field: null,
        old_value: null,
        new_value: null,
        user_id: user.id,
      });
      return undefined;
    }
  }

  const mediaMatch = /^\/media\/([^/]+)$/.exec(path);
  if (mediaMatch) {
    const media = findMedia(mediaMatch[1] as string, user);
    if (method === "PATCH") {
      const order = (body as { sort_order: number }).sort_order;
      if (order !== media.sort_order) {
        writeAudit({
          entity: "media",
          entity_id: media.id,
          action: "update",
          field: "sort_order",
          old_value: String(media.sort_order),
          new_value: String(order),
          user_id: user.id,
        });
        media.sort_order = order;
      }
      return toMedia(media);
    }
    if (method === "DELETE") {
      media.is_deleted = true;
      writeAudit({
        entity: "media",
        entity_id: media.id,
        action: "delete",
        field: null,
        old_value: null,
        new_value: null,
        user_id: user.id,
      });
      return undefined;
    }
  }

  const userMatch = /^\/users\/([^/]+)(\/[a-z-]+)?$/.exec(path);
  if (userMatch) {
    if (user.role !== "admin") throw forbidden();
    const target = state.users.find((item) => item.id === userMatch[1]);
    if (target === undefined) throw notFound("Пользователь не найден");
    if (userMatch[2] === "/reset-password") return undefined;
    const patch = body as Partial<Pick<User, "full_name" | "role" | "is_active">>;
    if (target.id === user.id && (patch.is_active === false || (patch.role && patch.role !== user.role))) {
      throw new ApiError(403, "SELF_MODIFICATION", "Нельзя изменить свою роль или отключить себя");
    }
    for (const [field, value] of Object.entries(patch)) {
      if (value === undefined || value === null) continue;
      const before = target[field as keyof User];
      if (before === value) continue;
      Object.assign(target, { [field]: value });
      writeAudit({
        entity: "user",
        entity_id: target.id,
        action: "update",
        field,
        old_value: String(before),
        new_value: String(value),
        user_id: user.id,
      });
    }
    return target;
  }

  if (path === "/users" && method === "POST") {
    if (user.role !== "admin") throw forbidden();
    const data = body as { username: string; full_name: string; role: Role };
    const username = data.username.trim().toLowerCase();
    if (state.users.some((item) => item.username === username)) {
      throw new ApiError(409, "USERNAME_TAKEN", "Пользователь с таким логином уже существует");
    }
    const created: User = {
      id: `user-${Date.now()}`,
      username,
      full_name: data.full_name,
      role: data.role,
      is_active: true,
      created_at: nowIso(),
    };
    state.users.push(created);
    writeAudit({
      entity: "user",
      entity_id: created.id,
      action: "create",
      field: "username",
      old_value: null,
      new_value: username,
      user_id: user.id,
    });
    return created;
  }

  const districtMatch = /^\/districts\/([^/]+)$/.exec(path);
  if (districtMatch && method === "PATCH") {
    if (user.role !== "admin") throw forbidden();
    const district = state.districts.find((item) => item.id === districtMatch[1]);
    if (district === undefined) throw notFound("Район не найден");
    const patch = body as Partial<District>;
    for (const [field, value] of Object.entries(patch)) {
      if (value === undefined || value === null) continue;
      const before = district[field as keyof District];
      if (before === value) continue;
      Object.assign(district, { [field]: value });
      writeAudit({
        entity: "district",
        entity_id: district.id,
        action: "update",
        field,
        old_value: String(before),
        new_value: String(value),
        user_id: user.id,
      });
    }
    return district;
  }
  if (path === "/districts" && method === "POST") {
    if (user.role !== "admin") throw forbidden();
    const name = (body as { name: string }).name.trim();
    if (state.districts.some((item) => item.name === name)) {
      throw new ApiError(409, "DISTRICT_EXISTS", "Район с таким названием уже существует");
    }
    const district: District = { id: `district-${Date.now()}`, name, is_active: true };
    state.districts.push(district);
    writeAudit({
      entity: "district",
      entity_id: district.id,
      action: "create",
      field: "name",
      old_value: null,
      new_value: name,
      user_id: user.id,
    });
    return district;
  }

  throw notFound();
}

export async function demoRequest<T>(path: string, options: RequestOptions): Promise<T> {
  const [route_, search = ""] = path.split("?");
  const query = new URLSearchParams(search);
  for (const [key, value] of Object.entries(options.query ?? {})) {
    if (value === undefined || value === null || value === "") continue;
    if (Array.isArray(value)) value.forEach((item) => query.append(key, String(item)));
    else query.append(key, String(value));
  }
  // A short delay keeps loading states visible, as with a real network.
  await new Promise((resolve) => setTimeout(resolve, 80));
  const result = route(options.method ?? "GET", route_ as string, query, options.json);
  saveDemoState();
  return result as T;
}

export async function demoUpload<T>(path: string, form: FormData): Promise<T> {
  const match = /^\/properties\/([^/]+)\/media$/.exec(path);
  if (match === null) throw notFound();
  await new Promise((resolve) => setTimeout(resolve, 120));
  return (await uploadMedia(match[1] as string, form, currentUser())) as T;
}

export function demoHasSession(): boolean {
  return demoState().current_user_id !== null;
}

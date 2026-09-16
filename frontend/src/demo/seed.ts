import type { AuditAction, District, InterestStatus, MediaKind, Role, User } from "../api/types";

/** Demo records mirror the API entities, minus what the server would keep private. */
export interface DemoProperty {
  id: string;
  code: number;
  request_no: string | null;
  district_id: string;
  landmark: string;
  owner_name: string | null;
  owner_phone: string;
  interest_status: InterestStatus;
  free_until: string | null;
  occupied_until: string | null;
  price: string | null;
  note: string | null;
  is_deleted: boolean;
  created_by: string;
  created_at: string;
  updated_by: string | null;
  updated_at: string | null;
}

export interface DemoMedia {
  id: string;
  property_id: string;
  kind: MediaKind;
  original_name: string | null;
  mime_type: string;
  size_bytes: number;
  sort_order: number;
  is_deleted: boolean;
  uploaded_by: string;
  uploaded_at: string;
  url: string;
  thumb_url: string | null;
}

export interface DemoAudit {
  id: number;
  entity: string;
  entity_id: string | null;
  action: AuditAction;
  field: string | null;
  old_value: string | null;
  new_value: string | null;
  user_id: string | null;
  ip: string | null;
  created_at: string;
}

export interface DemoView {
  id: number;
  property_id: string;
  user_id: string;
  viewed_at: string;
  ip: string | null;
}

export interface DemoState {
  version: number;
  current_user_id: string | null;
  users: User[];
  districts: District[];
  properties: DemoProperty[];
  media: DemoMedia[];
  audit: DemoAudit[];
  views: DemoView[];
  next_code: number;
  next_audit_id: number;
  next_view_id: number;
}

export const DEMO_STATE_VERSION = 5;
export const DEMO_IP = "192.168.1.24";

/** Deterministic generator, so everyone opening the demo sees the same base. */
function createRandom(seed: number): () => number {
  let state = seed;
  return () => {
    state = (state * 1103515245 + 12345) % 2147483648;
    return state / 2147483648;
  };
}

const DISTRICT_NAMES = [
  "Алмазарский", "Бектемирский", "Мирабадский", "Мирзо-Улугбекский", "Сергелийский",
  "Учтепинский", "Чиланзарский", "Шайхантахурский", "Юнусабадский", "Яккасарайский",
  "Яшнабадский", "Янгихаётский",
]; // prettier-ignore

const PEOPLE: { username: string; full_name: string; role: Role }[] = [
  { username: "admin", full_name: "Азиз Рахимов", role: "admin" },
  { username: "head", full_name: "Гульнора Юсупова", role: "head" },
  { username: "dilnoza", full_name: "Дилноза Каримова", role: "agent" },
  { username: "rustam", full_name: "Рустам Ахмедов", role: "agent" },
  { username: "sergey", full_name: "Сергей Петров", role: "agent" },
];

const LANDMARKS = [
  "рядом с метро Чиланзар, дом 9",
  "ул. Бунёдкор 14, ориентир Самарканд Дарвоза",
  "Юнусабад 4 квартал, напротив школы 110",
  "метро Ойбек, 5 минут пешком, новостройка",
  "ТЦ Некст, 12 этаж, вид на город",
  "Ц-1, за Анхором, тихий двор",
  "массив Кадышева, дом 3, второй этаж",
  "Мирзо-Улугбек, метро Буюк Ипак Йули",
  "Сергели 6, рядом с рынком",
  "Фархадский базар, дом 21",
  "Алайский базар, сталинка, 3 этаж",
  "Tashkent City, ЖК Бошлик, 8 этаж",
  "Минор, у речки, коттедж с садом",
  "рядом с метро Пушкин, кирпичный дом",
  "Ипподром, трёхкомнатная, ремонт 2024",
  "метро Новза, ул. Катартал 60",
  "Шайхантахур, махалля, отдельный вход",
  "Яккасарай, ул. Шота Руставели 23",
  "метро Беруни, 15 минут от центра",
  "Яшнабад, за парком Навруз",
];

const OWNER_NAMES = ["Иван", "Азиз", "Ольга", "Шахзод", "Малика", "Тимур", null, null];
const OPERATORS = ["90", "91", "93", "94", "97", "99"];
const NOTES = [
  "Хозяин на связи после 18:00",
  "Только семейным",
  "Можно с животными",
  "Торг уместен",
  null,
  null,
];
const TILE_COLORS = ["#b45309", "#1d4ed8", "#15803d", "#7c3aed", "#be123c", "#0f766e"];

function isoDaysAgo(days: number, hour = 10, minute = 0): string {
  const date = new Date();
  date.setUTCDate(date.getUTCDate() - days);
  date.setUTCHours(hour, minute, 0, 0);
  return date.toISOString();
}

function isoDaysAhead(days: number): string {
  const date = new Date();
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}

/** A small SVG stands in for a photo: no binary files are needed for the demo. */
function picture(color: string, caption: string, width: number, height: number): string {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 400 300">
<rect width="400" height="300" fill="${color}"/>
<rect y="200" width="400" height="100" fill="rgba(0,0,0,0.25)"/>
<g fill="rgba(255,255,255,0.85)">
<rect x="40" y="120" width="70" height="80"/><rect x="130" y="90" width="80" height="110"/>
<rect x="230" y="130" width="60" height="70"/><rect x="310" y="100" width="50" height="100"/>
</g>
<text x="200" y="265" font-family="system-ui, sans-serif" font-size="26" fill="#fff" text-anchor="middle">${caption}</text>
</svg>`;
  return `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`;
}

export function buildDemoState(): DemoState {
  const random = createRandom(20260916);
  const pick = <T,>(items: readonly T[]): T => items[Math.floor(random() * items.length)] as T;

  const users: User[] = PEOPLE.map((person, index) => ({
    id: `user-${index + 1}`,
    username: person.username,
    full_name: person.full_name,
    role: person.role,
    is_active: person.username !== "sergey",
    created_at: isoDaysAgo(400 - index * 20),
  }));
  const districts: District[] = DISTRICT_NAMES.map((name, index) => ({
    id: `district-${index + 1}`,
    name,
    is_active: name !== "Бектемирский",
  }));
  const agents = users.filter((user) => user.role !== "admin");

  const properties: DemoProperty[] = [];
  const media: DemoMedia[] = [];
  const audit: DemoAudit[] = [];
  const views: DemoView[] = [];
  let auditId = 1;
  let viewId = 1;

  const addAudit = (row: Omit<DemoAudit, "id" | "ip">): void => {
    audit.push({ ...row, id: auditId++, ip: DEMO_IP });
  };

  for (let index = 0; index < 42; index += 1) {
    const creator = pick(agents);
    const createdDaysAgo = 1 + Math.floor(random() * 120);
    const createdAt = isoDaysAgo(createdDaysAgo, 9 + Math.floor(random() * 9), 15);
    const occupied = random() < 0.4;
    const property: DemoProperty = {
      id: `property-${index + 1}`,
      code: 1000 + index,
      request_no: random() < 0.75 ? String(10000 + Math.floor(random() * 89999)) : null,
      district_id: pick(districts).id,
      landmark: LANDMARKS[index % LANDMARKS.length] as string,
      owner_name: pick(OWNER_NAMES),
      owner_phone: `+998 ${pick(OPERATORS)} ${100 + Math.floor(random() * 899)}-${
        10 + Math.floor(random() * 89)
      }-${10 + Math.floor(random() * 89)}`,
      interest_status: pick(["hot", "warm", "cold"] as InterestStatus[]),
      free_until: !occupied && random() < 0.5 ? isoDaysAhead(20 + Math.floor(random() * 180)) : null,
      occupied_until: occupied ? isoDaysAhead(5 + Math.floor(random() * 150)) : null,
      price: random() < 0.85 ? `${300 + Math.floor(random() * 18) * 50}` : null,
      note: pick(NOTES),
      is_deleted: index === 40,
      created_by: creator.id,
      created_at: createdAt,
      updated_by: null,
      updated_at: null,
    };
    properties.push(property);

    for (const [field, value] of Object.entries({
      request_no: property.request_no,
      district_id: property.district_id,
      landmark: property.landmark,
      owner_name: property.owner_name,
      owner_phone: property.owner_phone,
      interest_status: property.interest_status,
      free_until: property.free_until,
      occupied_until: property.occupied_until,
      price: property.price,
      note: property.note,
    })) {
      if (value !== null) {
        addAudit({
          entity: "property",
          entity_id: property.id,
          action: "create",
          field,
          old_value: null,
          new_value: String(value),
          user_id: creator.id,
          created_at: createdAt,
        });
      }
    }

    if (random() < 0.45) {
      const editor = random() < 0.3 ? (users[1] as User) : creator;
      const editedAt = isoDaysAgo(Math.max(0, createdDaysAgo - 1 - Math.floor(random() * 20)), 15, 40);
      const newStatus: InterestStatus = property.interest_status === "hot" ? "warm" : "hot";
      addAudit({
        entity: "property",
        entity_id: property.id,
        action: "update",
        field: "interest_status",
        old_value: property.interest_status,
        new_value: newStatus,
        user_id: editor.id,
        created_at: editedAt,
      });
      if (property.price !== null) {
        const newPrice = String(Number(property.price) - 50);
        addAudit({
          entity: "property",
          entity_id: property.id,
          action: "update",
          field: "price",
          old_value: property.price,
          new_value: newPrice,
          user_id: editor.id,
          created_at: editedAt,
        });
        property.price = newPrice;
      }
      property.interest_status = newStatus;
      property.updated_by = editor.id;
      property.updated_at = editedAt;
    }

    if (index === 40) {
      addAudit({
        entity: "property",
        entity_id: property.id,
        action: "delete",
        field: null,
        old_value: null,
        new_value: null,
        user_id: users[1]?.id ?? creator.id,
        created_at: isoDaysAgo(2, 12, 0),
      });
      property.updated_by = users[1]?.id ?? creator.id;
      property.updated_at = isoDaysAgo(2, 12, 0);
    }

    if (random() < 0.65) {
      const count = 1 + Math.floor(random() * 3);
      const color = pick(TILE_COLORS);
      for (let position = 0; position < count; position += 1) {
        const mediaId = `media-${property.id}-${position}`;
        const name = `фото_${position + 1}.jpg`;
        media.push({
          id: mediaId,
          property_id: property.id,
          kind: "photo",
          original_name: name,
          mime_type: "image/jpeg",
          size_bytes: 900_000 + Math.floor(random() * 2_000_000),
          sort_order: position,
          is_deleted: false,
          uploaded_by: creator.id,
          uploaded_at: createdAt,
          url: picture(color, `№ ${property.code} · ${position + 1}`, 1200, 900),
          thumb_url: picture(color, `№ ${property.code}`, 400, 300),
        });
        addAudit({
          entity: "media",
          entity_id: mediaId,
          action: "create",
          field: "original_name",
          old_value: null,
          new_value: name,
          user_id: creator.id,
          created_at: createdAt,
        });
        addAudit({
          entity: "media",
          entity_id: mediaId,
          action: "create",
          field: "kind",
          old_value: null,
          new_value: "photo",
          user_id: creator.id,
          created_at: createdAt,
        });
      }
    }
  }

  // A few days of card opens, so the "Просмотры" tab has something to show.
  for (const user of agents) {
    const opens = user.username === "rustam" ? 26 : 6 + Math.floor(random() * 8);
    for (let index = 0; index < opens; index += 1) {
      const property = properties[Math.floor(random() * properties.length)] as DemoProperty;
      if (property.is_deleted) continue;
      views.push({
        id: viewId++,
        property_id: property.id,
        user_id: user.id,
        viewed_at: isoDaysAgo(Math.floor(random() * 3), 8 + Math.floor(random() * 10), index),
        ip: DEMO_IP,
      });
    }
  }

  for (const user of users) {
    addAudit({
      entity: "user",
      entity_id: user.id,
      action: "login",
      field: null,
      old_value: null,
      new_value: null,
      user_id: user.id,
      created_at: isoDaysAgo(0, 7, 30),
    });
  }

  return {
    version: DEMO_STATE_VERSION,
    current_user_id: null,
    users,
    districts,
    properties,
    media,
    audit,
    views,
    next_code: 1000 + properties.length,
    next_audit_id: auditId,
    next_view_id: viewId,
  };
}

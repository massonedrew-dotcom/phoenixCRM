import type { AuditAction, InterestStatus, Role } from "../api/types";

export const TIME_ZONE = "Asia/Tashkent";

const dateFormat = new Intl.DateTimeFormat("ru-RU", {
  timeZone: TIME_ZONE,
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
});
const dateTimeFormat = new Intl.DateTimeFormat("ru-RU", {
  timeZone: TIME_ZONE,
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
});
const moneyFormat = new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 2 });

/** A calendar date (YYYY-MM-DD) as DD.MM.YYYY, without time zone shifts. */
export function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  const [year, month, day] = value.slice(0, 10).split("-");
  return `${day}.${month}.${year}`;
}

export function formatDateTime(value: string | null | undefined): string {
  return value ? dateTimeFormat.format(new Date(value)) : "—";
}

export function formatTimestampDate(value: string | null | undefined): string {
  return value ? dateFormat.format(new Date(value)) : "—";
}

/** Today's calendar date in Tashkent as YYYY-MM-DD. */
export function todayInTashkent(): string {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: TIME_ZONE,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date());
  return parts;
}

export function formatMoney(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === "") return "—";
  const number = typeof value === "number" ? value : Number(value);
  return Number.isFinite(number) ? moneyFormat.format(number) : "—";
}

/** Сум equivalent of a price in у.е.; null when the input is not a valid number. */
export function priceInUzs(priceUe: string, rate: string | undefined): number | null {
  if (!priceUe.trim() || rate === undefined) return null;
  const price = Number(priceUe.replace(",", "."));
  const perUe = Number(rate);
  if (!Number.isFinite(price) || !Number.isFinite(perUe)) return null;
  return Math.round(price * perUe * 100) / 100;
}

export const STATUS_LABELS: Record<InterestStatus, string> = {
  hot: "Горячий",
  warm: "Тёплый",
  cold: "Холодный",
};

export const ROLE_LABELS: Record<Role, string> = {
  admin: "Администратор",
  head: "Руководитель",
  agent: "Риелтор",
};

export const ACTION_LABELS: Record<AuditAction, string> = {
  create: "Создание",
  update: "Изменение",
  delete: "Удаление",
  restore: "Восстановление",
  login: "Вход",
  login_failed: "Неудачный вход",
  logout: "Выход",
};

export const ENTITY_LABELS: Record<string, string> = {
  property: "Карточка",
  media: "Файл",
  user: "Пользователь",
  district: "Район",
};

export const FIELD_LABELS: Record<string, string> = {
  request_no: "№ заявки",
  district_id: "Район",
  landmark: "Ориентир",
  owner_name: "Имя владельца",
  owner_phone: "Телефон владельца",
  interest_status: "Статус",
  free_until: "Свободна до",
  occupied_until: "Занята до",
  price: "Цена, у.е.",
  note: "Заметка",
  property_id: "Карточка",
  kind: "Тип файла",
  original_name: "Имя файла",
  sort_order: "Порядок",
  username: "Логин",
  full_name: "ФИО",
  role: "Роль",
  is_active: "Активен",
  password: "Пароль",
  name: "Название",
};

export type Availability = { label: string; tone: "free" | "occupied" };

export function availability(occupiedUntil: string | null, freeUntil: string | null): Availability {
  const today = todayInTashkent();
  if (occupiedUntil !== null && occupiedUntil >= today) {
    return { label: `Занята до ${formatDate(occupiedUntil)}`, tone: "occupied" };
  }
  if (freeUntil !== null) {
    return { label: `Свободна до ${formatDate(freeUntil)}`, tone: "free" };
  }
  return { label: "Свободна", tone: "free" };
}

export function formatFileSize(bytes: number): string {
  if (bytes >= 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} МБ`;
  return `${Math.max(1, Math.round(bytes / 1024))} КБ`;
}

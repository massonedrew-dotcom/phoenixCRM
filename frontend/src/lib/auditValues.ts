import type { InterestStatus, Role } from "../api/types";
import { ROLE_LABELS, STATUS_LABELS, formatDate, formatMoney } from "./format";

/** Human-readable form of a stored audit value, shared by the card history and the journal. */
export function formatAuditValue(
  field: string | null,
  value: string | null,
  districtNames: ReadonlyMap<string, string>,
): string {
  if (value === null || value === "") return "—";
  switch (field) {
    case "district_id":
      return districtNames.get(value) ?? "район не найден";
    case "interest_status":
      return STATUS_LABELS[value as InterestStatus] ?? value;
    case "free_until":
    case "occupied_until":
      return formatDate(value);
    case "price":
      return `${formatMoney(value)} у.е.`;
    case "kind":
      return value === "video" ? "видео" : "фото";
    case "role":
      return ROLE_LABELS[value as Role] ?? value;
    case "is_active":
      return value === "true" ? "да" : "нет";
    case "property_id":
      return "карточка";
    default:
      return value;
  }
}

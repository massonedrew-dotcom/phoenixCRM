import type { InterestStatus, Property, PropertyFields } from "../../api/types";

/** Form values are kept as strings; empty strings mean "not set". */
export interface FormValues {
  request_no: string;
  district_id: string;
  landmark: string;
  owner_name: string;
  owner_phone: string;
  interest_status: InterestStatus;
  free_until: string;
  occupied_until: string;
  price: string;
  note: string;
}

export const EMPTY_FORM: FormValues = {
  request_no: "",
  district_id: "",
  landmark: "",
  owner_name: "",
  owner_phone: "",
  interest_status: "warm",
  free_until: "",
  occupied_until: "",
  price: "",
  note: "",
};

export function toFormValues(property: Property): FormValues {
  return {
    request_no: property.request_no ?? "",
    district_id: property.district.id,
    landmark: property.landmark,
    owner_name: property.owner_name ?? "",
    owner_phone: property.owner_phone,
    interest_status: property.interest_status,
    free_until: property.free_until ?? "",
    occupied_until: property.occupied_until ?? "",
    price: property.price === null ? "" : trimPrice(property.price),
    note: property.note ?? "",
  };
}

function trimPrice(price: string): string {
  return price.endsWith(".00") ? price.slice(0, -3) : price;
}

function normalizePrice(value: string): string | null {
  const trimmed = value.trim().replace(",", ".").replace(/\s/g, "");
  return trimmed === "" ? null : trimmed;
}

function orNull(value: string): string | null {
  const trimmed = value.trim();
  return trimmed === "" ? null : trimmed;
}

export function toFields(values: FormValues): PropertyFields {
  return {
    request_no: orNull(values.request_no),
    district_id: values.district_id,
    landmark: values.landmark.trim(),
    owner_name: orNull(values.owner_name),
    owner_phone: values.owner_phone.trim(),
    interest_status: values.interest_status,
    free_until: orNull(values.free_until),
    occupied_until: orNull(values.occupied_until),
    price: normalizePrice(values.price),
    note: orNull(values.note),
  };
}

/** Only the fields whose normalized value differs, for a partial PATCH. */
export function changedFields(initial: FormValues, current: FormValues): Partial<PropertyFields> {
  const before = toFields(initial);
  const after = toFields(current);
  const patch: Partial<PropertyFields> = {};
  (Object.keys(after) as (keyof PropertyFields)[]).forEach((key) => {
    const same =
      key === "price"
        ? Number(before.price ?? NaN) === Number(after.price ?? NaN) ||
          (before.price === null && after.price === null)
        : before[key] === after[key];
    if (!same) {
      Object.assign(patch, { [key]: after[key] });
    }
  });
  return patch;
}

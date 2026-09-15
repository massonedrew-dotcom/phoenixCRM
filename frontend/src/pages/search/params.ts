import type { InterestStatus, SearchParams, SortOption } from "../../api/types";

const STATUSES: InterestStatus[] = ["hot", "warm", "cold"];
const SORTS: SortOption[] = ["created_at", "-created_at", "updated_at", "-updated_at", "code", "-code"];

export const PAGE_SIZE = 50;

/** Search state lives in the URL so that Back and shared links restore the same list. */
export function readSearchParams(url: URLSearchParams): SearchParams {
  const params: SearchParams = { page_size: PAGE_SIZE };
  const q = url.get("q")?.trim();
  if (q) params.q = q;
  const districts = url.getAll("district_id");
  if (districts.length) params.district_id = districts;
  const statuses = url.getAll("status").filter((s): s is InterestStatus =>
    STATUSES.includes(s as InterestStatus),
  );
  if (statuses.length) params.status = statuses;
  const availability = url.get("availability");
  if (availability === "free" || availability === "occupied") params.availability = availability;
  const freeFrom = url.get("free_from");
  if (freeFrom) params.free_from = freeFrom;
  const realtors = url.getAll("created_by");
  if (realtors.length) params.created_by = realtors;
  const createdFrom = url.get("created_from");
  if (createdFrom) params.created_from = createdFrom;
  const createdTo = url.get("created_to");
  if (createdTo) params.created_to = createdTo;
  const hasMedia = url.get("has_media");
  if (hasMedia === "true" || hasMedia === "false") params.has_media = hasMedia;
  const sort = url.get("sort");
  if (sort && SORTS.includes(sort as SortOption)) params.sort = sort as SortOption;
  const page = Number(url.get("page"));
  if (Number.isInteger(page) && page > 1) params.page = page;
  return params;
}

export function writeSearchParams(params: SearchParams): URLSearchParams {
  const url = new URLSearchParams();
  if (params.q) url.set("q", params.q);
  params.district_id?.forEach((id) => url.append("district_id", id));
  params.status?.forEach((status) => url.append("status", status));
  if (params.availability) url.set("availability", params.availability);
  if (params.free_from) url.set("free_from", params.free_from);
  params.created_by?.forEach((id) => url.append("created_by", id));
  if (params.created_from) url.set("created_from", params.created_from);
  if (params.created_to) url.set("created_to", params.created_to);
  if (params.has_media) url.set("has_media", params.has_media);
  if (params.sort) url.set("sort", params.sort);
  if (params.page && params.page > 1) url.set("page", String(params.page));
  return url;
}

export function activeFilterCount(params: SearchParams): number {
  return [
    params.district_id?.length,
    params.status?.length,
    params.availability,
    params.free_from,
    params.created_by?.length,
    params.created_from || params.created_to,
    params.has_media,
  ].filter(Boolean).length;
}

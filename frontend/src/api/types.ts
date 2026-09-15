export type Role = "admin" | "head" | "agent";
export type InterestStatus = "hot" | "warm" | "cold";
export type MediaKind = "photo" | "video";
export type AuditAction =
  | "create"
  | "update"
  | "delete"
  | "restore"
  | "login"
  | "login_failed"
  | "logout";
export type SortOption =
  | "created_at"
  | "-created_at"
  | "updated_at"
  | "-updated_at"
  | "code"
  | "-code";

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface UserRef {
  id: string;
  full_name: string;
}

export interface User {
  id: string;
  username: string;
  full_name: string;
  role: Role;
  is_active: boolean;
  created_at: string;
}

export interface Realtor {
  id: string;
  full_name: string;
  is_active: boolean;
}

export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user: User;
}

export interface District {
  id: string;
  name: string;
  is_active: boolean;
}

export interface ClientConfig {
  uzs_per_ue: string;
  max_photo_mb: number;
  max_video_mb: number;
  time_zone: string;
}

export interface Media {
  id: string;
  kind: MediaKind;
  original_name: string | null;
  mime_type: string;
  size_bytes: number;
  sort_order: number;
  uploaded_at: string;
  url: string;
  thumb_url: string | null;
}

export interface PropertyFields {
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
}

export interface Property extends Omit<PropertyFields, "district_id"> {
  id: string;
  code: number;
  deal_type: "rent" | "sale";
  district: { id: string; name: string };
  price_uzs: string | null;
  is_deleted: boolean;
  created_by: UserRef;
  created_at: string;
  updated_by: UserRef | null;
  updated_at: string | null;
  media: Media[];
  can_edit: boolean;
}

export interface PropertyListItem {
  id: string;
  code: number;
  district_name: string;
  landmark: string;
  interest_status: InterestStatus;
  free_until: string | null;
  occupied_until: string | null;
  created_by_name: string;
  created_at: string;
  updated_by_name: string | null;
  updated_at: string | null;
  cover_thumb_url: string | null;
  media_count: number;
}

export interface DeletedPropertyItem {
  id: string;
  code: number;
  district_name: string;
  landmark: string;
  created_by_name: string;
  deleted_by_name: string | null;
  deleted_at: string | null;
}

export interface AuditEntry {
  id: number;
  entity: string;
  entity_id: string | null;
  action: AuditAction;
  field: string | null;
  old_value: string | null;
  new_value: string | null;
  user: UserRef | null;
  ip: string | null;
  created_at: string;
  property_id?: string | null;
  property_code?: number | null;
  subject_name?: string | null;
}

export interface UserViewSummary {
  user_id: string;
  full_name: string;
  username: string;
  role: Role;
  is_active: boolean;
  views: number;
  cards: number;
  last_viewed_at: string;
}

export interface ViewEntry {
  id: number;
  viewed_at: string;
  user: UserRef;
  property: { id: string; code: number; landmark: string };
  ip: string | null;
}

export interface ViewFilter {
  user_id?: string;
  property_code?: number;
  date_from?: string;
  date_to?: string;
  page?: number;
  page_size?: number;
}

export interface SearchParams {
  q?: string;
  district_id?: string[];
  status?: InterestStatus[];
  availability?: "free" | "occupied";
  free_from?: string;
  created_by?: string[];
  created_from?: string;
  created_to?: string;
  has_media?: "true" | "false";
  sort?: SortOption;
  page?: number;
  page_size?: number;
}

export interface AuditFilter {
  entity?: string;
  action?: AuditAction;
  user_id?: string;
  property_code?: number;
  date_from?: string;
  date_to?: string;
  page?: number;
  page_size?: number;
}

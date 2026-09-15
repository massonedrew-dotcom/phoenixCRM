import {
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
  type UseQueryResult,
} from "@tanstack/react-query";

import { request, upload } from "./client";
import type {
  AuditEntry,
  AuditFilter,
  ClientConfig,
  DeletedPropertyItem,
  District,
  Media,
  Page,
  Property,
  PropertyFields,
  PropertyListItem,
  Realtor,
  Role,
  SearchParams,
  User,
  UserViewSummary,
  ViewEntry,
  ViewFilter,
} from "./types";

export const queryKeys = {
  me: ["me"] as const,
  config: ["config"] as const,
  districts: ["districts"] as const,
  realtors: ["realtors"] as const,
  users: ["users"] as const,
  search: (params: SearchParams) => ["properties", "search", params] as const,
  property: (id: string) => ["properties", "detail", id] as const,
  history: (id: string) => ["properties", "history", id] as const,
  deleted: (page: number) => ["properties", "deleted", page] as const,
  audit: (filter: AuditFilter) => ["audit", filter] as const,
  viewSummary: (from?: string, to?: string) => ["views", "summary", from, to] as const,
  views: (filter: ViewFilter) => ["views", "list", filter] as const,
};

const REFERENCE_STALE_MS = 5 * 60 * 1000;

export function useConfig(): UseQueryResult<ClientConfig> {
  return useQuery({
    queryKey: queryKeys.config,
    queryFn: () => request<ClientConfig>("/config"),
    staleTime: Infinity,
  });
}

export function useDistricts(): UseQueryResult<District[]> {
  return useQuery({
    queryKey: queryKeys.districts,
    queryFn: () => request<District[]>("/districts"),
    staleTime: REFERENCE_STALE_MS,
  });
}

export function useRealtors(): UseQueryResult<Realtor[]> {
  return useQuery({
    queryKey: queryKeys.realtors,
    queryFn: () => request<Realtor[]>("/realtors"),
    staleTime: REFERENCE_STALE_MS,
  });
}

export function useSearch(params: SearchParams): UseQueryResult<Page<PropertyListItem>> {
  return useQuery({
    queryKey: queryKeys.search(params),
    queryFn: () => request<Page<PropertyListItem>>("/properties", { query: { ...params } }),
    placeholderData: keepPreviousData,
  });
}

export function useProperty(id: string | undefined): UseQueryResult<Property> {
  return useQuery({
    queryKey: queryKeys.property(id ?? ""),
    queryFn: () => request<Property>(`/properties/${id}`),
    enabled: id !== undefined,
  });
}

export function usePropertyHistory(id: string, enabled: boolean): UseQueryResult<AuditEntry[]> {
  return useQuery({
    queryKey: queryKeys.history(id),
    queryFn: () => request<AuditEntry[]>(`/properties/${id}/history`),
    enabled,
  });
}

function useInvalidateProperties(): (id?: string) => Promise<void> {
  const client = useQueryClient();
  return async (id?: string) => {
    await client.invalidateQueries({ queryKey: ["properties", "search"] });
    await client.invalidateQueries({ queryKey: ["properties", "deleted"] });
    await client.invalidateQueries({ queryKey: ["audit"] });
    if (id !== undefined) {
      await client.invalidateQueries({ queryKey: queryKeys.property(id) });
      await client.invalidateQueries({ queryKey: queryKeys.history(id) });
    }
  };
}

export function useCreateProperty() {
  const invalidate = useInvalidateProperties();
  return useMutation({
    mutationFn: (fields: PropertyFields) =>
      request<Property>("/properties", { method: "POST", json: fields }),
    onSuccess: async () => invalidate(),
  });
}

export function useUpdateProperty(id: string) {
  const client = useQueryClient();
  const invalidate = useInvalidateProperties();
  return useMutation({
    mutationFn: (patch: Partial<PropertyFields>) =>
      request<Property>(`/properties/${id}`, { method: "PATCH", json: patch }),
    onSuccess: async (property) => {
      client.setQueryData(queryKeys.property(id), property);
      await invalidate(id);
    },
  });
}

export function useDeleteProperty(id: string) {
  const invalidate = useInvalidateProperties();
  return useMutation({
    mutationFn: () => request<void>(`/properties/${id}`, { method: "DELETE" }),
    onSuccess: async () => invalidate(id),
  });
}

export function useRestoreProperty() {
  const invalidate = useInvalidateProperties();
  return useMutation({
    mutationFn: (id: string) =>
      request<Property>(`/properties/${id}/restore`, { method: "POST" }),
    onSuccess: async (property) => invalidate(property.id),
  });
}

export function useUploadMedia(propertyId: string) {
  const invalidate = useInvalidateProperties();
  return useMutation({
    mutationFn: ({ files, onProgress }: { files: File[]; onProgress: (fraction: number) => void }) => {
      const form = new FormData();
      files.forEach((file) => form.append("files", file, file.name));
      return upload<Media[]>(`/properties/${propertyId}/media`, form, onProgress);
    },
    onSuccess: async () => invalidate(propertyId),
  });
}

export function useReorderMedia(propertyId: string) {
  const invalidate = useInvalidateProperties();
  return useMutation({
    mutationFn: async (changes: { id: string; sort_order: number }[]) => {
      for (const change of changes) {
        await request<Media>(`/media/${change.id}`, {
          method: "PATCH",
          json: { sort_order: change.sort_order },
        });
      }
    },
    onSettled: async () => invalidate(propertyId),
  });
}

export function useDeleteMedia(propertyId: string) {
  const invalidate = useInvalidateProperties();
  return useMutation({
    mutationFn: (mediaId: string) => request<void>(`/media/${mediaId}`, { method: "DELETE" }),
    onSuccess: async () => invalidate(propertyId),
  });
}

export function useDeletedProperties(page: number): UseQueryResult<Page<DeletedPropertyItem>> {
  return useQuery({
    queryKey: queryKeys.deleted(page),
    queryFn: () =>
      request<Page<DeletedPropertyItem>>("/properties/deleted", { query: { page } }),
    placeholderData: keepPreviousData,
  });
}

export function useAuditFeed(filter: AuditFilter): UseQueryResult<Page<AuditEntry>> {
  return useQuery({
    queryKey: queryKeys.audit(filter),
    queryFn: () => request<Page<AuditEntry>>("/audit", { query: { ...filter } }),
    placeholderData: keepPreviousData,
  });
}

export function useUsers(): UseQueryResult<User[]> {
  return useQuery({ queryKey: queryKeys.users, queryFn: () => request<User[]>("/users") });
}

function useInvalidateUsers(): () => Promise<void> {
  const client = useQueryClient();
  return async () => {
    await client.invalidateQueries({ queryKey: queryKeys.users });
    await client.invalidateQueries({ queryKey: queryKeys.realtors });
  };
}

export interface NewUser {
  username: string;
  full_name: string;
  password: string;
  role: Role;
}

export function useCreateUser() {
  const invalidate = useInvalidateUsers();
  return useMutation({
    mutationFn: (user: NewUser) => request<User>("/users", { method: "POST", json: user }),
    onSuccess: async () => invalidate(),
  });
}

export function useUpdateUser() {
  const invalidate = useInvalidateUsers();
  return useMutation({
    mutationFn: ({ id, patch }: { id: string; patch: Partial<Pick<User, "full_name" | "role" | "is_active">> }) =>
      request<User>(`/users/${id}`, { method: "PATCH", json: patch }),
    onSuccess: async () => invalidate(),
  });
}

export function useResetPassword() {
  return useMutation({
    mutationFn: ({ id, password }: { id: string; password: string }) =>
      request<void>(`/users/${id}/reset-password`, {
        method: "POST",
        json: { new_password: password },
      }),
  });
}

export function useChangePassword() {
  return useMutation({
    mutationFn: (body: { old_password: string; new_password: string }) =>
      request<void>("/auth/change-password", { method: "POST", json: body }),
  });
}

export function useCreateDistrict() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (name: string) => request<District>("/districts", { method: "POST", json: { name } }),
    onSuccess: async () => client.invalidateQueries({ queryKey: queryKeys.districts }),
  });
}

export function useUpdateDistrict() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id, patch }: { id: string; patch: Partial<Pick<District, "name" | "is_active">> }) =>
      request<District>(`/districts/${id}`, { method: "PATCH", json: patch }),
    onSuccess: async () => client.invalidateQueries({ queryKey: queryKeys.districts }),
  });
}

export function useViewSummary(
  dateFrom: string | undefined,
  dateTo: string | undefined,
): UseQueryResult<UserViewSummary[]> {
  return useQuery({
    queryKey: queryKeys.viewSummary(dateFrom, dateTo),
    queryFn: () =>
      request<UserViewSummary[]>("/views/summary", {
        query: { date_from: dateFrom, date_to: dateTo },
      }),
    placeholderData: keepPreviousData,
  });
}

export function useViews(filter: ViewFilter, enabled = true): UseQueryResult<Page<ViewEntry>> {
  return useQuery({
    queryKey: queryKeys.views(filter),
    queryFn: () => request<Page<ViewEntry>>("/views", { query: { ...filter } }),
    placeholderData: keepPreviousData,
    enabled,
  });
}
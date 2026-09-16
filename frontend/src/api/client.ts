import { ApiError, type FieldError } from "./errors";

export { ApiError };
export type { FieldError };

const API_BASE = "/api/v1";
const REFRESH_TOKEN_KEY = "crm.refreshToken";

/** The GitHub Pages build answers requests from a demo database in the browser. */
const DEMO = import.meta.env.VITE_DEMO === "1";
const demoApi = () => import("../demo/api");

let accessToken: string | null = null;
let refreshInFlight: Promise<boolean> | null = null;
let authLostListener: () => void = () => undefined;

function readRefreshToken(): string | null {
  try {
    return localStorage.getItem(REFRESH_TOKEN_KEY);
  } catch {
    return null;
  }
}

function writeRefreshToken(token: string | null): void {
  try {
    if (token === null) {
      localStorage.removeItem(REFRESH_TOKEN_KEY);
    } else {
      localStorage.setItem(REFRESH_TOKEN_KEY, token);
    }
  } catch {
    // Storage can be unavailable (private mode); the session then lasts until reload.
  }
}

export const session = {
  start(access: string, refresh: string): void {
    accessToken = access;
    writeRefreshToken(refresh);
  },
  clear(): void {
    accessToken = null;
    writeRefreshToken(null);
  },
  hasRefreshToken(): boolean {
    // In the demo the session lives in the demo database, not in a token.
    return DEMO || readRefreshToken() !== null;
  },
  onAuthLost(listener: () => void): void {
    authLostListener = listener;
  },
};

/** Exchange the stored refresh token for a new access token. Concurrent callers share one request. */
export function refreshAccessToken(): Promise<boolean> {
  if (refreshInFlight === null) {
    refreshInFlight = (async () => {
      if (DEMO) {
        return (await demoApi()).demoHasSession();
      }
      const refreshToken = readRefreshToken();
      if (refreshToken === null) {
        return false;
      }
      try {
        const response = await fetch(`${API_BASE}/auth/refresh`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ refresh_token: refreshToken }),
        });
        if (!response.ok) {
          return false;
        }
        const body = (await response.json()) as { access_token: string };
        accessToken = body.access_token;
        return true;
      } catch {
        return false;
      }
    })().finally(() => {
      refreshInFlight = null;
    });
  }
  return refreshInFlight;
}

type QueryValue = string | number | boolean | null | undefined | readonly (string | number)[];

export function buildUrl(path: string, query?: Record<string, QueryValue>): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query ?? {})) {
    if (value === undefined || value === null || value === "") {
      continue;
    }
    if (Array.isArray(value)) {
      value.forEach((item) => params.append(key, String(item)));
    } else {
      params.append(key, String(value));
    }
  }
  const search = params.toString();
  return `${API_BASE}${path}${search ? `?${search}` : ""}`;
}

const VALIDATION_MESSAGES: Record<string, string> = {
  missing: "Обязательное поле",
  string_too_long: "Слишком длинное значение",
  string_too_short: "Слишком короткое значение",
  string_pattern_mismatch: "Недопустимые символы",
  greater_than_equal: "Значение не может быть отрицательным",
  less_than_equal: "Слишком большое значение",
  decimal_max_places: "Не больше двух знаков после запятой",
  decimal_max_digits: "Слишком большое число",
  decimal_parsing: "Введите число",
  uuid_parsing: "Выберите значение из списка",
  uuid_type: "Выберите значение из списка",
  date_from_datetime_parsing: "Некорректная дата",
  date_parsing: "Некорректная дата",
  enum: "Выберите значение из списка",
};

interface ValidationIssue {
  type: string;
  loc: (string | number)[];
  msg: string;
}

function validationMessage(issue: ValidationIssue): string {
  if (issue.msg.startsWith("Value error, ")) {
    return issue.msg.slice("Value error, ".length);
  }
  return VALIDATION_MESSAGES[issue.type] ?? "Некорректное значение";
}

async function toApiError(response: Response): Promise<ApiError> {
  let body: unknown = null;
  try {
    body = await response.json();
  } catch {
    // Non-JSON error, e.g. nginx 502 page.
  }
  if (body !== null && typeof body === "object" && "detail" in body) {
    const detail = (body as { detail: unknown; code?: string }).detail;
    const code = (body as { code?: string }).code ?? `HTTP_${response.status}`;
    if (typeof detail === "string") {
      return new ApiError(response.status, code, detail);
    }
    if (Array.isArray(detail)) {
      const fieldErrors = (detail as ValidationIssue[]).map((issue) => ({
        field: String(issue.loc[issue.loc.length - 1] ?? ""),
        message: validationMessage(issue),
      }));
      return new ApiError(
        response.status,
        "VALIDATION_ERROR",
        "Проверьте правильность заполнения полей",
        fieldErrors,
      );
    }
  }
  if (response.status >= 500) {
    return new ApiError(response.status, "SERVER_ERROR", "Сервер временно недоступен. Повторите попытку");
  }
  return new ApiError(response.status, `HTTP_${response.status}`, "Не удалось выполнить запрос");
}

export interface RequestOptions {
  method?: "GET" | "POST" | "PATCH" | "DELETE";
  json?: unknown;
  form?: FormData;
  query?: Record<string, QueryValue>;
}

async function send(path: string, options: RequestOptions): Promise<Response> {
  const headers: Record<string, string> = {};
  if (accessToken !== null) {
    headers.Authorization = `Bearer ${accessToken}`;
  }
  let body: BodyInit | undefined;
  if (options.form !== undefined) {
    body = options.form;
  } else if (options.json !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(options.json);
  }
  try {
    return await fetch(buildUrl(path, options.query), {
      method: options.method ?? "GET",
      headers,
      body,
    });
  } catch {
    throw new ApiError(0, "NETWORK_ERROR", "Нет связи с сервером. Проверьте подключение");
  }
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  if (DEMO) {
    return (await demoApi()).demoRequest<T>(path, options);
  }
  let response = await send(path, options);
  if (response.status === 401 && session.hasRefreshToken()) {
    if (await refreshAccessToken()) {
      response = await send(path, options);
    }
  }
  if (response.status === 401) {
    session.clear();
    authLostListener();
  }
  if (!response.ok) {
    throw await toApiError(response);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

/** Multipart upload with progress; retries once after refreshing an expired token. */
export function upload<T>(
  path: string,
  form: FormData,
  onProgress: (fraction: number) => void,
): Promise<T> {
  if (DEMO) {
    onProgress(1);
    return demoApi().then((api) => api.demoUpload<T>(path, form));
  }
  const attempt = (): Promise<{ status: number; text: string }> =>
    new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open("POST", buildUrl(path));
      if (accessToken !== null) {
        xhr.setRequestHeader("Authorization", `Bearer ${accessToken}`);
      }
      xhr.upload.onprogress = (event) => {
        if (event.lengthComputable) {
          onProgress(event.loaded / event.total);
        }
      };
      xhr.onload = () => resolve({ status: xhr.status, text: xhr.responseText });
      xhr.onerror = () =>
        reject(new ApiError(0, "NETWORK_ERROR", "Нет связи с сервером. Проверьте подключение"));
      xhr.send(form);
    });

  return (async () => {
    let result = await attempt();
    if (result.status === 401 && (await refreshAccessToken())) {
      result = await attempt();
    }
    const response = new Response(result.text || null, {
      status: result.status,
      headers: { "Content-Type": "application/json" },
    });
    if (result.status === 401) {
      session.clear();
      authLostListener();
    }
    if (!response.ok) {
      throw await toApiError(response);
    }
    return (await response.json()) as T;
  })();
}

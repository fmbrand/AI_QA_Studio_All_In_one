// API client: keeps the short-lived access token in memory, refreshes it through the httpOnly cookie,
// and turns RFC 9457 problem responses into ApiError.

import type { Envelope, TokenResponse } from "./types";

export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

export interface FieldError {
  field: string;
  message: string;
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly errors: FieldError[];
  readonly body: Record<string, unknown>;

  constructor(status: number, code: string, message: string, errors: FieldError[] = [], body = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.errors = errors;
    this.body = body;
  }

  fieldError(field: string): string | undefined {
    return this.errors.find((e) => e.field === field)?.message;
  }
}

export async function toApiError(res: Response): Promise<ApiError> {
  let body: Record<string, unknown> = {};
  try {
    body = (await res.json()) as Record<string, unknown>;
  } catch {
    // Non-JSON error (proxy, network appliance): fall back to the status text.
  }
  const detail = typeof body.detail === "string" ? body.detail : res.statusText || "Request failed";
  const code = typeof body.code === "string" ? body.code : `http_${res.status}`;
  const errors = Array.isArray(body.errors) ? (body.errors as FieldError[]) : [];
  return new ApiError(res.status, code, detail, errors, body);
}

let accessToken: string | null = null;
let refreshing: Promise<TokenResponse | null> | null = null;
let onSessionExpired: (() => void) | null = null;

export function setAccessToken(token: string | null) {
  accessToken = token;
}

export function setSessionExpiredHandler(handler: (() => void) | null) {
  onSessionExpired = handler;
}

/** Exchange the refresh cookie for a new access token. Concurrent callers share one request. */
export function refreshSession(): Promise<TokenResponse | null> {
  if (!refreshing) {
    refreshing = (async () => {
      try {
        const res = await fetch(`${API_URL}/api/v1/auth/refresh`, { method: "POST", credentials: "include" });
        if (!res.ok) {
          accessToken = null;
          return null;
        }
        const body = (await res.json()) as Envelope<TokenResponse>;
        accessToken = body.data.access_token;
        return body.data;
      } catch {
        return null;
      } finally {
        setTimeout(() => (refreshing = null), 0);
      }
    })();
  }
  return refreshing;
}

export interface RequestOptions {
  method?: string;
  body?: unknown;
  form?: FormData;
  ifMatch?: number;
  signal?: AbortSignal;
}

async function send(path: string, opts: RequestOptions): Promise<Response> {
  const headers: Record<string, string> = {};
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`;
  if (opts.ifMatch !== undefined) headers["If-Match"] = `"${opts.ifMatch}"`;
  let body: BodyInit | undefined;
  if (opts.form) {
    body = opts.form;
  } else if (opts.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(opts.body);
  }
  return fetch(`${API_URL}/api/v1${path}`, {
    method: opts.method ?? "GET",
    headers,
    body,
    credentials: "include",
    signal: opts.signal,
  });
}

/** Call the API. Retries once after refreshing the session on 401. Returns the full envelope. */
export async function request<T>(path: string, opts: RequestOptions = {}): Promise<Envelope<T>> {
  let res = await send(path, opts);
  if (res.status === 401 && !path.startsWith("/auth/")) {
    const refreshed = await refreshSession();
    if (refreshed) {
      res = await send(path, opts);
    } else {
      onSessionExpired?.();
    }
  }
  if (!res.ok) throw await toApiError(res);
  if (res.status === 204) return { data: undefined as T, meta: { request_id: null, page: null } };
  return (await res.json()) as Envelope<T>;
}

export const api = {
  get: <T>(path: string, signal?: AbortSignal) => request<T>(path, { signal }).then((r) => r.data),
  page: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) => request<T>(path, { method: "POST", body }).then((r) => r.data),
  upload: <T>(path: string, form: FormData) => request<T>(path, { method: "POST", form }).then((r) => r.data),
  patch: <T>(path: string, body: unknown, ifMatch?: number) =>
    request<T>(path, { method: "PATCH", body, ifMatch }).then((r) => r.data),
  put: <T>(path: string, body: unknown) => request<T>(path, { method: "PUT", body }).then((r) => r.data),
  delete: (path: string) => request<void>(path, { method: "DELETE" }).then(() => undefined),
};

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof TypeError) return "Cannot reach the server. Check that the API is running.";
  return "Something went wrong. Please try again.";
}

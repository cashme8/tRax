/**
 * The one place that talks HTTP to the Django API.
 *
 * - Adds `Authorization: Bearer <access>` and `X-Company-ID: <active company>`.
 * - If the access token has expired (401), refreshes it once and retries.
 * - Turns DRF error bodies into an ApiError with per-field messages.
 */

import { session } from "@/lib/session";

const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

/** DRF error body flattened to "field" / "items.0.quantity" → messages. */
export type FieldErrors = Record<string, string[]>;

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public fieldErrors: FieldErrors = {},
  ) {
    super(message);
    this.name = "ApiError";
  }
}

type RequestOptions = {
  method?: "GET" | "POST" | "PATCH" | "DELETE";
  body?: unknown;
  query?: Record<string, string | undefined>;
  /** Send the Bearer token (default true). */
  auth?: boolean;
  /**
   * The company this request is about, sent as X-Company-ID. Passed explicitly
   * by each call (not read from global state) so it always matches the
   * company in the caller's query key.
   */
  companyId?: string;
};

let refreshing: Promise<boolean> | null = null;

/** Get a new access token from the refresh token. Shared by concurrent requests. */
export function refreshAccessToken(): Promise<boolean> {
  refreshing ??= (async () => {
    const refresh = session.getRefresh();
    if (!refresh) return false;
    const response = await fetch(`${API_URL}/api/auth/refresh/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh }),
    });
    if (!response.ok) return false;
    const { access } = (await response.json()) as { access: string };
    session.setTokens(access);
    return true;
  })().finally(() => {
    refreshing = null;
  });
  return refreshing;
}

function buildUrl(path: string, query?: RequestOptions["query"]): string {
  const url = new URL(`${API_URL}${path}`);
  for (const [key, value] of Object.entries(query ?? {})) {
    if (value !== undefined && value !== "") url.searchParams.set(key, value);
  }
  return url.toString();
}

async function send(path: string, options: RequestOptions): Promise<Response> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (options.body !== undefined) headers["Content-Type"] = "application/json";
  const access = session.getAccess();
  if (options.auth !== false && access) headers.Authorization = `Bearer ${access}`;
  if (options.companyId) headers["X-Company-ID"] = options.companyId;

  return fetch(buildUrl(path, options.query), {
    method: options.method ?? "GET",
    headers,
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
  });
}

function flatten(value: unknown, prefix: string, out: FieldErrors): void {
  if (Array.isArray(value) && value.every((v) => typeof v === "string")) {
    out[prefix] = value as string[];
  } else if (typeof value === "string") {
    out[prefix] = [value];
  } else if (Array.isArray(value)) {
    value.forEach((v, i) => flatten(v, prefix ? `${prefix}.${i}` : String(i), out));
  } else if (value && typeof value === "object") {
    for (const [key, v] of Object.entries(value))
      flatten(v, prefix ? `${prefix}.${key}` : key, out);
  }
}

async function toApiError(response: Response): Promise<ApiError> {
  let body: unknown = null;
  try {
    body = await response.json();
  } catch {
    // not JSON (e.g. a 500 HTML page)
  }
  const fieldErrors: FieldErrors = {};
  flatten(body, "", fieldErrors);
  const general = [...(fieldErrors.detail ?? []), ...(fieldErrors.non_field_errors ?? [])];
  delete fieldErrors.detail;
  delete fieldErrors.non_field_errors;

  let message = general.join(" ");
  if (!message) {
    message =
      Object.keys(fieldErrors).length > 0
        ? "Please fix the highlighted fields."
        : response.status >= 500
          ? "The server had a problem. Please try again."
          : `Request failed (${response.status}).`;
  }
  return new ApiError(message, response.status, fieldErrors);
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  let response: Response;
  try {
    response = await send(path, options);
    if (response.status === 401 && options.auth !== false && (await refreshAccessToken())) {
      response = await send(path, options); // retry once with the new token
    }
  } catch {
    throw new ApiError("Can't reach the tRax server. Check your connection.", 0);
  }

  if (response.status === 401 && options.auth !== false) {
    session.clear(); // refresh failed: the session is over
  }
  if (!response.ok) throw await toApiError(response);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

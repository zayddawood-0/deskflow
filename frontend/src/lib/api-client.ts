import type { ErrorDetail } from "@/types/api";
import { REQUEST_TIMEOUT_MS } from "./constants";

const BASE = "/api/v1";

let accessToken: string | null = null;

export const AUTH_LOGOUT_EVENT = "auth:logout";

export function setAccessToken(token: string | null): void {
  accessToken = token;
}

export function getAccessToken(): string | null {
  return accessToken;
}

export class ApiError extends Error {
  constructor(
    public readonly code: string,
    message: string,
    public readonly status: number,
    public readonly details?: ErrorDetail[],
  ) {
    super(message);
    this.name = "ApiError";
  }
}

let refreshPromise: Promise<boolean> | null = null;

async function tryRefresh(): Promise<boolean> {
  if (!refreshPromise) {
    refreshPromise = (async () => {
      try {
        const res = await fetch(`${BASE}/auth/refresh`, {
          method: "POST",
          credentials: "same-origin",
          signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
        });
        if (!res.ok) {
          return false;
        }
        const data = (await res.json()) as { access_token: string };
        accessToken = data.access_token;
        return true;
      } catch {
        return false;
      } finally {
        refreshPromise = null;
      }
    })();
  }
  return refreshPromise;
}

export async function api<T>(
  path: string,
  init: RequestInit & { json?: unknown } = {},
): Promise<T> {
  const { json, headers, signal, ...rest } = init;

  const doFetch = (): Promise<Response> =>
    fetch(`${BASE}${path}`, {
      ...rest,
      credentials: "same-origin",
      signal: signal ?? AbortSignal.timeout(REQUEST_TIMEOUT_MS),
      headers: {
        ...(json !== undefined ? { "Content-Type": "application/json" } : {}),
        ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
        ...headers,
      },
      ...(json !== undefined ? { body: JSON.stringify(json) } : {}),
    });

  let res = await doFetch();

  if (res.status === 401) {
    const refreshed = await tryRefresh();
    if (refreshed) {
      res = await doFetch();
    } else {
      accessToken = null;
      if (typeof window !== "undefined") {
        window.dispatchEvent(new Event(AUTH_LOGOUT_EVENT));
      }
    }
  }

  if (!res.ok) {
    type ParsedError = {
      error?: { code?: string; message?: string; details?: ErrorDetail[] };
    };
    let envelope: ParsedError | null = null;
    try {
      envelope = (await res.json()) as ParsedError;
    } catch {
      envelope = null;
    }
    throw new ApiError(
      envelope?.error?.code ?? "INTERNAL_ERROR",
      envelope?.error?.message ?? `Request failed with status ${res.status}`,
      res.status,
      envelope?.error?.details,
    );
  }

  if (res.status === 204) {
    return undefined as T;
  }
  return (await res.json()) as T;
}

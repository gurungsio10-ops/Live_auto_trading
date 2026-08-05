/**
 * Server-side FastAPI client. Secrets stay on the server;
 * browser code only talks to Next.js /api proxy routes.
 */

import { resolveBackendUrl } from "@/lib/runtime";

export function backendBaseUrl(): string {
  return resolveBackendUrl();
}

export class BackendError extends Error {
  status: number;
  endpoint: string;
  correlationId: string;

  constructor(
    message: string,
    status = 502,
    opts?: { endpoint?: string; correlationId?: string },
  ) {
    super(message);
    this.name = "BackendError";
    this.status = status;
    this.endpoint = opts?.endpoint ?? "";
    this.correlationId = opts?.correlationId ?? "";
  }
}

export async function backendFetch<T>(
  path: string,
  init?: RequestInit & { timeoutMs?: number },
): Promise<T> {
  const { timeoutMs = 8000, ...rest } = init ?? {};
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  const base = backendBaseUrl();
  const endpoint = `${base}${path}`;
  const correlationId =
    (typeof rest.headers === "object" &&
      rest.headers !== null &&
      !Array.isArray(rest.headers) &&
      "X-Correlation-ID" in rest.headers &&
      typeof (rest.headers as Record<string, string>)["X-Correlation-ID"] === "string" &&
      (rest.headers as Record<string, string>)["X-Correlation-ID"]) ||
    crypto.randomUUID();

  try {
    const res = await fetch(endpoint, {
      ...rest,
      signal: controller.signal,
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "X-Correlation-ID": correlationId,
        "X-Request-ID": correlationId,
        ...(rest.headers ?? {}),
      },
      cache: "no-store",
    });

    if (!res.ok) {
      const body = await res.text().catch(() => "");
      throw new BackendError(
        `Backend ${res.status} on ${path}${body ? `: ${body.slice(0, 200)}` : ""}`,
        res.status,
        { endpoint, correlationId },
      );
    }

    if (res.status === 204) {
      return undefined as T;
    }

    return (await res.json()) as T;
  } catch (err) {
    if (err instanceof BackendError) throw err;
    const message =
      err instanceof Error ? err.message : "Unknown backend connectivity error";
    throw new BackendError(`Backend unreachable (${base}): ${message}`, 503, {
      endpoint,
      correlationId,
    });
  } finally {
    clearTimeout(timer);
  }
}

export function envelope<T>(
  data: T,
  demo: boolean,
  backend_error?: string,
): { data: T; meta: { demo: boolean; backend_error?: string } } {
  return {
    data,
    meta: backend_error ? { demo, backend_error } : { demo },
  };
}

/** Headers for mutating FastAPI endpoints protected by ADMIN_API_TOKEN. */
export function adminHeaders(
  extra?: Record<string, string>,
): Record<string, string> {
  const token =
    process.env.ADMIN_API_TOKEN ?? process.env.ATLAS_ADMIN_API_TOKEN ?? "";
  const headers: Record<string, string> = { ...(extra ?? {}) };
  if (token) {
    headers["X-Admin-Token"] = token;
  }
  return headers;
}

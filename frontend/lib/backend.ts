/**
 * Server-side FastAPI client. Secrets stay on the server;
 * browser code only talks to Next.js /api proxy routes.
 */

const BACKEND_URL =
  process.env.ATLAS_BACKEND_URL ?? "http://127.0.0.1:8000";

export class BackendError extends Error {
  status: number;

  constructor(message: string, status = 502) {
    super(message);
    this.name = "BackendError";
    this.status = status;
  }
}

export async function backendFetch<T>(
  path: string,
  init?: RequestInit & { timeoutMs?: number },
): Promise<T> {
  const { timeoutMs = 2500, ...rest } = init ?? {};
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const res = await fetch(`${BACKEND_URL}${path}`, {
      ...rest,
      signal: controller.signal,
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        ...(rest.headers ?? {}),
      },
      cache: "no-store",
    });

    if (!res.ok) {
      const body = await res.text().catch(() => "");
      throw new BackendError(
        `Backend ${res.status} on ${path}${body ? `: ${body.slice(0, 200)}` : ""}`,
        res.status,
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
    throw new BackendError(`Backend unreachable (${BACKEND_URL}): ${message}`, 503);
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

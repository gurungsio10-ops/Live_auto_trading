import { NextRequest, NextResponse } from "next/server";
import { backendBaseUrl, backendFetch, BackendError } from "@/lib/backend";
import { SESSION_COOKIE, SESSION_MAX_AGE, REMEMBER_MAX_AGE } from "@/lib/auth";
import { isDevDiagnosticsEnabled, sessionCookieOptions } from "@/lib/runtime";

export const dynamic = "force-dynamic";

/**
 * Login is delegated to the FastAPI backend, which owns the user store
 * (hashed passwords) and issues the signed session token. We then set that
 * token as the httpOnly cookie; the middleware verifies it locally via the
 * shared ATLAS_AUTH_SECRET.
 *
 * Browser → same-origin `/api/auth/login` (works on Codespaces HTTPS).
 * Next.js server → loopback `ATLAS_BACKEND_URL` (default http://127.0.0.1:8000).
 */
export async function POST(req: NextRequest) {
  let body: { username?: string; password?: string; remember?: boolean };
  try {
    body = (await req.json()) as {
      username?: string;
      password?: string;
      remember?: boolean;
    };
  } catch {
    body = {};
  }

  const username = (body.username ?? "").trim();
  const password = body.password ?? "";
  const remember = Boolean(body.remember);
  const correlationId = crypto.randomUUID();
  const endpoint = `${backendBaseUrl()}/auth/login`;

  try {
    const data = await backendFetch<{ token: string; username: string }>(
      "/auth/login",
      {
        method: "POST",
        body: JSON.stringify({ username, password, remember }),
        timeoutMs: 10000,
        headers: {
          "X-Correlation-ID": correlationId,
          "X-Request-ID": correlationId,
        },
      },
    );
    const maxAge = remember ? REMEMBER_MAX_AGE : SESSION_MAX_AGE;
    const res = NextResponse.json({
      data: { username: data.username },
      meta: { demo: false },
    });
    res.cookies.set(SESSION_COOKIE, data.token, sessionCookieOptions(req, maxAge));
    res.headers.set("X-Correlation-ID", correlationId);
    return res;
  } catch (err) {
    const upstreamStatus = err instanceof BackendError ? err.status : null;
    const upstreamMessage = err instanceof Error ? err.message : String(err);

    // Structured server log — no passwords, no secrets.
    console.error(
      JSON.stringify({
        event: "atlas.auth.login.upstream_failure",
        correlation_id: correlationId,
        endpoint,
        upstream_status: upstreamStatus,
        message: upstreamMessage.slice(0, 500),
      }),
    );

    if (err instanceof BackendError && err.status === 401) {
      return NextResponse.json(
        { error: "Invalid username or password", correlation_id: correlationId },
        { status: 401, headers: { "X-Correlation-ID": correlationId } },
      );
    }

    const payload: Record<string, unknown> = {
      error: "Authentication service unavailable. Please try again.",
      code: "AUTH_UPSTREAM_UNAVAILABLE",
      correlation_id: correlationId,
    };
    if (isDevDiagnosticsEnabled()) {
      const unreachable =
        upstreamStatus == null ||
        upstreamStatus === 503 ||
        /unreachable|ECONNREFUSED|fetch failed|aborted/i.test(upstreamMessage);
      // Safe diagnostics for local/Codespaces operators (no secrets).
      payload.detail = {
        endpoint,
        upstream_status: upstreamStatus,
        hint: unreachable
          ? "Backend not reachable from Next.js. Start FastAPI on 0.0.0.0:8000 and set ATLAS_BACKEND_URL=http://127.0.0.1:8000."
          : "Backend returned a non-auth error. Check API logs, DATABASE_URL, and `alembic upgrade head`.",
      };
    }
    return NextResponse.json(payload, {
      status: 503,
      headers: { "X-Correlation-ID": correlationId },
    });
  }
}

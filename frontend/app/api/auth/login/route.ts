import { NextRequest, NextResponse } from "next/server";
import { backendFetch, BackendError } from "@/lib/backend";
import { SESSION_COOKIE, SESSION_MAX_AGE, REMEMBER_MAX_AGE } from "@/lib/auth";

export const dynamic = "force-dynamic";

/**
 * Login is delegated to the FastAPI backend, which owns the user store
 * (hashed passwords) and issues the signed session token. We then set that
 * token as the httpOnly cookie; the middleware verifies it locally via the
 * shared ATLAS_AUTH_SECRET.
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

  try {
    const data = await backendFetch<{ token: string; username: string }>(
      "/auth/login",
      {
        method: "POST",
        body: JSON.stringify({ username, password, remember }),
      },
    );
    const maxAge = remember ? REMEMBER_MAX_AGE : SESSION_MAX_AGE;
    const res = NextResponse.json({ data: { username: data.username }, meta: { demo: false } });
    res.cookies.set(SESSION_COOKIE, data.token, {
      httpOnly: true,
      sameSite: "lax",
      path: "/",
      maxAge,
      secure: process.env.NODE_ENV === "production",
    });
    return res;
  } catch (err) {
    if (err instanceof BackendError && err.status === 401) {
      return NextResponse.json({ error: "Invalid username or password" }, { status: 401 });
    }
    return NextResponse.json(
      { error: "Authentication service unavailable. Please try again." },
      { status: 503 },
    );
  }
}

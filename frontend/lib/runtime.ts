/**
 * Runtime helpers for local + GitHub Codespaces deployments.
 * Server-side only — never import cookie helpers into client components.
 */

import type { NextRequest } from "next/server";

export function isCodespaces(): boolean {
  return Boolean(
    process.env.CODESPACES === "true" ||
      process.env.CODESPACE_NAME ||
      process.env.GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN,
  );
}

export function isDevDiagnosticsEnabled(): boolean {
  const env = (process.env.APP_ENV ?? process.env.NODE_ENV ?? "development").toLowerCase();
  return env === "development" || env === "dev" || env === "test" || isCodespaces();
}

/**
 * Prefer loopback for server-side BFF → FastAPI calls.
 * Never use the public Codespaces forwarded backend URL from Node —
 * that path is for browsers and can break mixed-content / auth cookies.
 */
export function resolveBackendUrl(): string {
  const explicit = (process.env.ATLAS_BACKEND_URL ?? "").trim().replace(/\/$/, "");
  if (explicit) {
    return explicit;
  }
  return "http://127.0.0.1:8000";
}

/** Session cookie flags that work on localhost HTTP and Codespaces HTTPS. */
export function sessionCookieOptions(
  req: NextRequest | null,
  maxAge: number,
): {
  httpOnly: true;
  sameSite: "lax";
  path: "/";
  maxAge: number;
  secure: boolean;
} {
  const forwardedProto = req?.headers.get("x-forwarded-proto");
  const isHttps =
    forwardedProto === "https" ||
    req?.nextUrl.protocol === "https:" ||
    isCodespaces();
  return {
    httpOnly: true,
    sameSite: "lax",
    path: "/",
    maxAge,
    // Secure cookies on HTTPS / Codespaces; plain HTTP local dev stays insecure.
    secure: process.env.NODE_ENV === "production" || isHttps,
  };
}

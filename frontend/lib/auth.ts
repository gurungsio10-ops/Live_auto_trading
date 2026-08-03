/**
 * Isomorphic session helpers for the Atlas Terminal dashboard.
 *
 * Uses the Web Crypto API only (HMAC-SHA256) so the same module works in both
 * Edge middleware and Node.js route handlers. Credentials and the signing
 * secret stay server-side — the browser only ever receives an httpOnly cookie.
 */

export const SESSION_COOKIE = "atlas_session";
export const SESSION_MAX_AGE = 60 * 60 * 8; // 8 hours

const encoder = new TextEncoder();
const decoder = new TextDecoder();

function authSecret(): string {
  return process.env.ATLAS_AUTH_SECRET ?? "atlas-dev-secret-change-me";
}

function base64urlEncode(bytes: Uint8Array): string {
  let binary = "";
  for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i]);
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function base64urlDecode(value: string): Uint8Array {
  const padded = value.replace(/-/g, "+").replace(/_/g, "/");
  const pad = padded.length % 4 === 0 ? "" : "=".repeat(4 - (padded.length % 4));
  const binary = atob(padded + pad);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return bytes;
}

async function hmacKey(): Promise<CryptoKey> {
  return crypto.subtle.importKey(
    "raw",
    encoder.encode(authSecret()),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign", "verify"],
  );
}

export interface Session {
  username: string;
  exp: number;
}

export async function createSessionToken(username: string): Promise<string> {
  const payload: Session = {
    username,
    exp: Math.floor(Date.now() / 1000) + SESSION_MAX_AGE,
  };
  const body = base64urlEncode(encoder.encode(JSON.stringify(payload)));
  const signature = await crypto.subtle.sign("HMAC", await hmacKey(), encoder.encode(body));
  return `${body}.${base64urlEncode(new Uint8Array(signature))}`;
}

export async function verifySessionToken(token?: string | null): Promise<Session | null> {
  if (!token) return null;
  const [body, signature] = token.split(".");
  if (!body || !signature) return null;

  let valid = false;
  try {
    valid = await crypto.subtle.verify(
      "HMAC",
      await hmacKey(),
      base64urlDecode(signature) as BufferSource,
      encoder.encode(body),
    );
  } catch {
    return null;
  }
  if (!valid) return null;

  try {
    const payload = JSON.parse(decoder.decode(base64urlDecode(body))) as Session;
    if (!payload.username || typeof payload.exp !== "number") return null;
    if (payload.exp < Math.floor(Date.now() / 1000)) return null;
    return payload;
  } catch {
    return null;
  }
}

/**
 * Validate submitted credentials against server-side config.
 * Defaults (admin / atlas) let the dashboard be exercised without extra setup;
 * override via ATLAS_DASHBOARD_USER / ATLAS_DASHBOARD_PASSWORD.
 */
export function verifyCredentials(username: string, password: string): boolean {
  const expectedUser = process.env.ATLAS_DASHBOARD_USER ?? "admin";
  const expectedPassword = process.env.ATLAS_DASHBOARD_PASSWORD ?? "atlas";
  return username === expectedUser && password === expectedPassword;
}

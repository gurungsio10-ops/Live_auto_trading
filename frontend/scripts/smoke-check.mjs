#!/usr/bin/env node
/**
 * Lightweight smoke checks for the Atlas dashboard.
 * Ensures ADMIN_API_TOKEN never appears in client-side component/page sources.
 */
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative, sep } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(fileURLToPath(new URL(".", import.meta.url)), "..");
const clientRoots = [join(root, "app"), join(root, "components"), join(root, "lib")];
const FORBIDDEN = "ADMIN_API_TOKEN";
const serverOnlyPrefixes = [join(root, "app", "api") + sep];

function walk(dir, out = []) {
  let entries;
  try {
    entries = readdirSync(dir);
  } catch {
    return out;
  }
  for (const name of entries) {
    const full = join(dir, name);
    let st;
    try {
      st = statSync(full);
    } catch {
      continue;
    }
    if (st.isDirectory()) {
      if (name === "node_modules" || name === ".next") continue;
      walk(full, out);
    } else if (/\.(tsx?|jsx?|mjs|cjs)$/.test(name)) {
      out.push(full);
    }
  }
  return out;
}

const offenders = [];
for (const base of clientRoots) {
  for (const file of walk(base)) {
    if (serverOnlyPrefixes.some((p) => file.startsWith(p))) continue;
    // Server-only backend helper may reference admin env vars.
    if (file.endsWith(`${sep}backend.ts`) || file.includes(`${sep}backend.`)) continue;
    const text = readFileSync(file, "utf8");
    if (text.includes(FORBIDDEN)) {
      offenders.push(relative(root, file));
    }
  }
}

if (offenders.length) {
  console.error("smoke-check failed: ADMIN_API_TOKEN found in client-reachable sources:");
  for (const f of offenders) console.error(`  - ${f}`);
  process.exit(1);
}

console.log("smoke-check ok: ADMIN_API_TOKEN not present in client component paths");

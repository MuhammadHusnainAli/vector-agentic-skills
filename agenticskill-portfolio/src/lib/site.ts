import fs from "node:fs";
import path from "node:path";

import { SITE_URL } from "./constants";

export * from "./constants";

/** Repository root (this app lives one level below it). */
export const REPO_ROOT = path.resolve(process.cwd(), "..");

/**
 * Deployed version, e.g. "v0.1.7".
 * CI sets SITE_VERSION from git tags (major.minor from /VERSION, patch = deploy count).
 * Local builds fall back to "<VERSION>.0-dev".
 */
export function siteVersion(): string {
  if (process.env.SITE_VERSION) return process.env.SITE_VERSION;
  try {
    const base = fs.readFileSync(path.join(REPO_ROOT, "VERSION"), "utf8").trim();
    return `v${base}.0-dev`;
  } catch {
    return "v0.1.0-dev";
  }
}

/**
 * Base URL for the sitemap, robots.txt and canonical links.
 * `npm run dev` uses http://localhost:<PORT>; set SITE_URL to override (e.g. a local static
 * preview with `npm run build:local`). Production builds use the live domain.
 * Install commands always use the live domain (SITE_URL constant), since they must work anywhere.
 */
export function siteUrl(): string {
  const url =
    process.env.SITE_URL ||
    (process.env.NODE_ENV === "development" ? `http://localhost:${process.env.PORT || 3000}` : SITE_URL);
  return url.replace(/\/$/, "");
}

export function buildDate(): Date {
  return process.env.BUILD_DATE ? new Date(process.env.BUILD_DATE) : new Date();
}

export function formatDate(d: Date | string): string {
  return new Date(d)
    .toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" })
    .replace(",", "")
    .toUpperCase();
}

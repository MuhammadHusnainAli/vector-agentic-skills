import type { SearchEntry } from "@/lib/skills";

/** Open the command palette from anywhere. */
export function openPalette(query = "") {
  window.dispatchEvent(new CustomEvent("palette:open", { detail: query }));
}

/**
 * Rank skills against a query. Every whitespace-separated term must match
 * somewhere; name/title hits outrank description and heading hits.
 */
export function searchSkills(index: SearchEntry[], query: string): SearchEntry[] {
  const terms = query.toLowerCase().trim().split(/\s+/).filter(Boolean);
  if (!terms.length) return index;
  const scored: { e: SearchEntry; score: number }[] = [];
  for (const e of index) {
    const name = e.name.toLowerCase();
    const title = e.title.toLowerCase();
    const summary = e.summary.toLowerCase();
    const cat = e.categoryTitle.toLowerCase();
    let score = 0;
    let all = true;
    for (const t of terms) {
      let s = 0;
      if (name === t) s += 20;
      if (name.startsWith(t)) s += 10;
      if (name.includes(t)) s += 8;
      if (title.includes(t)) s += 6;
      if (cat.includes(t)) s += 4;
      if (summary.includes(t)) s += 3;
      if (e.keywords.includes(t)) s += 1;
      if (!s) {
        all = false;
        break;
      }
      score += s;
    }
    if (all) scored.push({ e, score });
  }
  return scored.sort((a, b) => b.score - a.score || a.e.name.localeCompare(b.e.name)).map((x) => x.e);
}

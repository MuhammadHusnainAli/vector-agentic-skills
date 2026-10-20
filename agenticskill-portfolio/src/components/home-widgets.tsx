"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import type { SearchEntry } from "@/lib/skills";
import { ArrowRight, Search } from "./icons";
import { openPalette, searchSkills } from "./search";

/** Inline search in the hero: results drop down as you type, Enter opens the top hit. */
export function HeroSearch({ index }: { index: SearchEntry[] }) {
  const router = useRouter();
  const [q, setQ] = useState("");
  const [active, setActive] = useState(0);
  const [focused, setFocused] = useState(false);
  const results = useMemo(() => (q.trim() ? searchSkills(index, q).slice(0, 6) : []), [index, q]);
  const examples = ["window functions", "slow query", "xlookup", "duplicates", "cohort"];

  const go = (name?: string) => name && router.push(`/skills/${name}/`);

  return (
    <div className="hero-search">
      <label className="hero-search-box">
        <Search />
        <span className="sr-only">Search skills</span>
        <input
          value={q}
          onChange={(e) => {
            setQ(e.target.value);
            setActive(0);
          }}
          onFocus={() => setFocused(true)}
          onBlur={() => setTimeout(() => setFocused(false), 150)}
          onKeyDown={(e) => {
            if (e.key === "ArrowDown") {
              e.preventDefault();
              setActive((a) => Math.min(a + 1, results.length - 1));
            } else if (e.key === "ArrowUp") {
              e.preventDefault();
              setActive((a) => Math.max(a - 1, 0));
            } else if (e.key === "Enter") {
              go(results[active]?.name);
            }
          }}
          placeholder="What should your agent get better at?"
          autoComplete="off"
          role="combobox"
          aria-expanded={focused && results.length > 0}
          aria-controls="hero-results"
        />
        <kbd className="hide-sm">⌘K</kbd>
        <button
          type="button"
          className="hero-search-go"
          aria-label="Search"
          onClick={() => (results[active] ? go(results[active].name) : openPalette(q))}
        >
          <ArrowRight />
        </button>
      </label>
      {focused && results.length > 0 && (
        <ul className="hero-results" id="hero-results" role="listbox">
          {results.map((r, i) => (
            <li key={r.name} role="option" aria-selected={i === active} onMouseEnter={() => setActive(i)}>
              <Link href={`/skills/${r.name}/`}>
                <b>{r.name}</b>
                <span>{r.summary}</span>
                <em>{r.subcategoryTitle}</em>
              </Link>
            </li>
          ))}
        </ul>
      )}
      <div className="hero-examples">
        <span className="label">Try</span>
        {examples.map((e) => (
          <button key={e} type="button" onClick={() => setQ(e)}>
            {e}
          </button>
        ))}
      </div>
    </div>
  );
}

"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import type { SearchEntry } from "@/lib/skills";
import { ArrowUpRight, Search } from "./icons";
import { searchSkills } from "./search";

type Sort = "relevance" | "name" | "updated";

function highlight(text: string, query: string) {
  const terms = query.trim().split(/\s+/).filter((t) => t.length > 1);
  if (!terms.length) return text;
  const re = new RegExp(`(${terms.map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|")})`, "ig");
  return text.split(re).map((part, i) => (i % 2 ? <mark key={i}>{part}</mark> : part));
}

export function SkillExplorer({
  index,
  categories,
}: {
  index: SearchEntry[];
  categories: { slug: string; title: string; count: number; subcategories: { slug: string; title: string; count: number }[] }[];
}) {
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("all");
  const [sort, setSort] = useState<Sort>("relevance");
  const [view, setView] = useState<"grid" | "list">("grid");

  // Deep links: /skills/?q=window&category=programming
  // Sync from the URL and storage after hydration; the prerendered HTML has no query.
  useEffect(() => {
    const p = new URLSearchParams(window.location.search);
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (p.get("q")) setQuery(p.get("q")!);
    if (p.get("category")) setCategory(p.get("category")!);
    try {
      const v = localStorage.getItem("explorer-view");
      if (v === "list" || v === "grid") setView(v);
    } catch {}
  }, []);

  useEffect(() => {
    const p = new URLSearchParams();
    if (query) p.set("q", query);
    if (category !== "all") p.set("category", category);
    const qs = p.toString();
    window.history.replaceState(null, "", qs ? `?${qs}` : window.location.pathname);
  }, [query, category]);

  const results = useMemo(() => {
    let r = searchSkills(index, query);
    if (category !== "all") r = r.filter((s) => `${s.category}/${s.subcategory}` === category || s.category === category);
    if (sort === "name" || (sort === "relevance" && !query)) r = [...r].sort((a, b) => a.name.localeCompare(b.name));
    if (sort === "updated") r = [...r].sort((a, b) => b.updated.localeCompare(a.updated));
    return r;
  }, [index, query, category, sort]);

  const setViewSaved = (v: "grid" | "list") => {
    setView(v);
    try {
      localStorage.setItem("explorer-view", v);
    } catch {}
  };

  return (
    <div className={view}>
      <div className="toolbar">
        <label className="search-input">
          <Search />
          <span className="sr-only">Search skills</span>
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search by name, topic or function — e.g. window, xlookup, slow query"
            autoComplete="off"
          />
          <span className="label" style={{ whiteSpace: "nowrap" }}>
            {results.length}/{index.length}
          </span>
        </label>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <div className="seg" role="group" aria-label="Sort">
            {(["relevance", "name", "updated"] as Sort[]).map((s) => (
              <button key={s} aria-pressed={sort === s} onClick={() => setSort(s)}>
                {s === "relevance" ? "Best" : s === "name" ? "A–Z" : "Recent"}
              </button>
            ))}
          </div>
          <div className="seg" role="group" aria-label="View">
            <button aria-pressed={view === "grid"} onClick={() => setViewSaved("grid")}>
              Grid
            </button>
            <button aria-pressed={view === "list"} onClick={() => setViewSaved("list")}>
              List
            </button>
          </div>
        </div>
        <div className="filters" role="group" aria-label="Category" style={{ gridColumn: "1 / -1" }}>
          <button aria-pressed={category === "all"} onClick={() => setCategory("all")}>
            All<small>{index.length}</small>
          </button>
          {categories.flatMap((c) =>
            c.subcategories.map((s) => {
              const key = `${c.slug}/${s.slug}`;
              return (
                <button key={key} aria-pressed={category === key} onClick={() => setCategory(key)}>
                  <span style={{ opacity: 0.55 }}>{c.title} /</span> {s.title}
                  <small>{s.count}</small>
                </button>
              );
            }),
          )}
        </div>
      </div>

      {results.length === 0 ? (
        <div className="empty">
          <b>Nothing matches “{query}”</b>
          Try another keyword, or{" "}
          <button
            className="text-link"
            style={{ display: "inline", border: 0, background: "none", cursor: "pointer", font: "inherit" }}
            onClick={() => {
              setQuery("");
              setCategory("all");
            }}
          >
            clear filters
          </button>
          .
        </div>
      ) : (
        <div className="cards">
          {results.map((s) => (
            <Link key={s.name} href={`/skills/${s.name}/`} className="card">
              <div className="top">
                <span className="badge">
                  {s.categoryTitle} / {s.subcategoryTitle}
                </span>
                <ArrowUpRight width={16} height={16} />
              </div>
              <h3>{highlight(s.name, query)}</h3>
              <p>{highlight(s.summary, query)}</p>
              <div className="meta">
                <span className="badge">SKILL.md</span>
                {s.files > 0 && <span className="badge">{s.files} refs</span>}
                {s.scripts > 0 && <span className="badge accent">{s.scripts === 1 ? "script" : `${s.scripts} scripts`}</span>}
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

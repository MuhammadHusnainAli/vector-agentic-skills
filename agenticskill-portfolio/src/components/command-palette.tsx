"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { SearchEntry } from "@/lib/skills";
import { Search } from "./icons";
import { searchSkills } from "./search";

type Item = { href: string; label: string; detail: string; tag: string; icon: string };

const PAGES: Item[] = [
  { href: "/skills/", label: "Browse all skills", detail: "Filter and sort the full index", tag: "page", icon: "↗" },
  { href: "/categories/", label: "Categories", detail: "Skills grouped by domain", tag: "page", icon: "↗" },
  { href: "/install/", label: "Install guide", detail: "npx skills, Claude Code plugin, curl, git", tag: "page", icon: "↗" },
];

export function CommandPalette({ index }: { index: SearchEntry[] }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLUListElement>(null);

  const items = useMemo<Item[]>(() => {
    const skills = searchSkills(index, query).map((s) => ({
      href: `/skills/${s.name}/`,
      label: s.name,
      detail: s.summary,
      tag: s.categoryTitle,
      icon: s.name.slice(0, 2).toUpperCase(),
    }));
    const q = query.trim().toLowerCase();
    const pages = q ? PAGES.filter((p) => p.label.toLowerCase().includes(q)) : PAGES;
    return [...skills, ...pages];
  }, [index, query]);

  const close = useCallback(() => setOpen(false), []);

  useEffect(() => {
    const onOpen = (e: Event) => {
      setQuery((e as CustomEvent<string>).detail ?? "");
      setActive(0);
      setOpen(true);
    };
    const onKey = (e: KeyboardEvent) => {
      const typing = (e.target as HTMLElement)?.closest?.("input, textarea, [contenteditable]");
      if ((e.key === "k" && (e.metaKey || e.ctrlKey)) || (e.key === "/" && !typing)) {
        e.preventDefault();
        setOpen((o) => !o);
        setQuery("");
        setActive(0);
      }
    };
    window.addEventListener("palette:open", onOpen);
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("palette:open", onOpen);
      window.removeEventListener("keydown", onKey);
    };
  }, []);

  useEffect(() => {
    if (!open) return;
    inputRef.current?.focus();
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, [open]);

  useEffect(() => {
    listRef.current?.querySelector(`[data-idx="${active}"]`)?.scrollIntoView({ block: "nearest" });
  }, [active]);

  if (!open) return null;

  const go = (item?: Item) => {
    if (!item) return;
    close();
    router.push(item.href);
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Escape") close();
    else if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((a) => Math.min(a + 1, items.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((a) => Math.max(a - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      go(items[active]);
    }
  };

  return (
    <div className="palette-backdrop" onMouseDown={(e) => e.target === e.currentTarget && close()}>
      <div className="palette" role="dialog" aria-modal="true" aria-label="Search skills">
        <div className="search-input">
          <Search />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setActive(0);
            }}
            onKeyDown={onKeyDown}
            placeholder="Search skills, topics, functions..."
            aria-label="Search"
            role="combobox"
            aria-expanded="true"
            aria-controls="palette-list"
            aria-activedescendant={`palette-item-${active}`}
          />
          <span className="kbd">ESC</span>
        </div>
        <ul className="palette-list" id="palette-list" role="listbox" ref={listRef}>
          {items.length === 0 && (
            <li className="empty" style={{ margin: 8 }}>
              <b>No skills match “{query}”</b>
              Try a broader term like “sql” or “excel”.
            </li>
          )}
          {items.map((item, i) => (
            <li
              key={item.href}
              id={`palette-item-${i}`}
              data-idx={i}
              role="option"
              aria-selected={i === active}
              className="palette-item"
              onMouseMove={() => setActive(i)}
              onClick={() => go(item)}
            >
              <span className="ico">{item.icon}</span>
              <span className="txt">
                <b>{item.label}</b>
                <span className="muted">{item.detail}</span>
              </span>
              <span className="badge">{item.tag}</span>
            </li>
          ))}
        </ul>
        <div className="palette-foot">
          <span>
            <span className="kbd">↑</span>
            <span className="kbd">↓</span> navigate
          </span>
          <span>
            <span className="kbd">↵</span> open
          </span>
          <span>
            <span className="kbd">/</span> or <span className="kbd">⌘K</span> toggle
          </span>
          <span style={{ marginLeft: "auto" }}>{items.length} results</span>
        </div>
      </div>
    </div>
  );
}

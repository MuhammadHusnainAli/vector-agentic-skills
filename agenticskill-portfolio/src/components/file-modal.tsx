"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ArrowUpRight, Close, CodeIcon, Download, FileIcon } from "./icons";
import { markPopupNavigation } from "./page-fade";

type FileRef = { slug: string; file: string; kind: "reference" | "script"; lines: number };
type Loaded = { html: string; isSource: boolean };

// Rendered file pages already exist as static HTML; the popup reuses them.
const cache = new Map<string, Promise<Loaded>>();

function load(url: string): Promise<Loaded> {
  let p = cache.get(url);
  if (!p) {
    p = fetch(url)
      .then((r) => {
        if (!r.ok) throw new Error(String(r.status));
        return r.text();
      })
      .then((text) => {
        const doc = new DOMParser().parseFromString(text, "text/html");
        const source = doc.querySelector("article figure.code.source");
        const prose = doc.querySelector("article .prose");
        const node = source ?? prose;
        if (!node) throw new Error("no content");
        return { html: node.outerHTML, isSource: Boolean(source) };
      });
    p.catch(() => cache.delete(url));
    cache.set(url, p);
  }
  return p;
}

/**
 * Opens a skill's reference and script files in a popup instead of navigating.
 * Links keep their real URLs, so new tabs, crawlers and direct visits still get full pages.
 */
export function FileModal({ skill, dir, files }: { skill: string; dir: string; files: FileRef[] }) {
  const [slug, setSlug] = useState<string | null>(null);
  const [content, setContent] = useState<Loaded | null>(null);
  const [error, setError] = useState(false);
  const bodyRef = useRef<HTMLDivElement>(null);
  const pushed = useRef(false);
  const base = `/skills/${skill}/`;

  const urlFor = useCallback((s: string) => `${base}${s}/`, [base]);
  const slugFromHref = useCallback(
    (href: string) => {
      const u = new URL(href, window.location.href);
      if (u.origin !== window.location.origin || !u.pathname.startsWith(base)) return null;
      const s = decodeURIComponent(u.pathname.slice(base.length).replace(/\/$/, ""));
      return files.some((f) => f.slug === s) ? s : null;
    },
    [base, files],
  );

  const show = useCallback(
    (s: string, mode: "push" | "replace" | "none") => {
      setSlug(s);
      setError(false);
      setContent(null);
      if (mode !== "none") markPopupNavigation();
      if (mode === "push" && !pushed.current) {
        history.pushState({ fileModal: s }, "", urlFor(s));
        pushed.current = true;
      } else if (mode !== "none") {
        history.replaceState({ fileModal: s }, "", urlFor(s));
      }
      load(urlFor(s))
        .then((c) => {
          setContent(c);
          bodyRef.current?.scrollTo({ top: 0 });
        })
        .catch(() => setError(true));
    },
    [urlFor],
  );

  const close = useCallback(() => {
    if (pushed.current) {
      pushed.current = false;
      markPopupNavigation();
      history.back(); // popstate clears the state below
    } else {
      setSlug(null);
    }
  }, []);

  // Intercept clicks on file links, and warm the cache on hover/focus.
  useEffect(() => {
    const target = (e: Event) => (e.target as HTMLElement).closest?.<HTMLAnchorElement>("a[href]");
    const onClick = (e: MouseEvent) => {
      const a = target(e);
      if (!a || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || a.target === "_blank") return;
      const s = slugFromHref(a.href);
      if (!s) return;
      e.preventDefault();
      e.stopPropagation();
      show(s, slug ? "replace" : "push");
    };
    const onWarm = (e: Event) => {
      const a = target(e);
      const s = a && slugFromHref(a.href);
      if (s) load(urlFor(s)).catch(() => {});
    };
    const onPop = () => {
      if (slug) markPopupNavigation(); // browser Back closing the popup
      pushed.current = false;
      setSlug(null);
    };
    document.addEventListener("click", onClick, true);
    document.addEventListener("pointerover", onWarm, { passive: true });
    document.addEventListener("focusin", onWarm);
    window.addEventListener("popstate", onPop);
    return () => {
      document.removeEventListener("click", onClick, true);
      document.removeEventListener("pointerover", onWarm);
      document.removeEventListener("focusin", onWarm);
      window.removeEventListener("popstate", onPop);
    };
  }, [show, slug, slugFromHref, urlFor]);

  useEffect(() => {
    if (!slug) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") close();
    };
    window.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = prev;
      window.removeEventListener("keydown", onKey);
    };
  }, [slug, close]);

  if (!slug) return null;
  const file = files.find((f) => f.slug === slug)!;

  // In-page anchors inside the popup scroll the popup, not the page behind it.
  const onBodyClick = (e: React.MouseEvent) => {
    const a = (e.target as HTMLElement).closest<HTMLAnchorElement>("a[href^='#']");
    if (!a) return;
    e.preventDefault();
    bodyRef.current?.querySelector(`[id="${CSS.escape(a.hash.slice(1))}"]`)?.scrollIntoView({ block: "start" });
  };

  return (
    <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && close()}>
      <div className="modal" role="dialog" aria-modal="true" aria-label={file.file}>
        <div className="modal-head">
          <div className="modal-title">
            <span className="modal-icon">{file.kind === "script" ? <CodeIcon /> : <FileIcon />}</span>
            <div>
              <span className="label">{skill}</span>
              <b>{file.file}</b>
            </div>
          </div>
          <div className="modal-actions">
            <a href={`/raw/${dir}/${file.file}`} target="_blank" rel="noopener" className="modal-btn" title="Raw file">
              <Download />
              <span className="hide-sm">Raw</span>
            </a>
            <a href={urlFor(slug)} target="_blank" rel="noopener" className="modal-btn" title="Open as page">
              <ArrowUpRight />
              <span className="hide-sm">Open page</span>
            </a>
            <button type="button" className="modal-btn modal-close" onClick={close} aria-label="Close">
              <Close />
            </button>
          </div>
        </div>
        {files.length > 1 && (
          <div className="modal-tabs" role="tablist" aria-label="Skill files">
            {files.map((f) => (
              <button
                key={f.slug}
                type="button"
                role="tab"
                aria-selected={f.slug === slug}
                onClick={() => f.slug !== slug && show(f.slug, "replace")}
              >
                {f.file.split("/").pop()}
                <small>{f.lines}</small>
              </button>
            ))}
          </div>
        )}
        <div className="modal-body" ref={bodyRef} onClick={onBodyClick}>
          {error ? (
            <div className="empty">
              <b>Couldn&apos;t load {file.file}</b>
              <a href={urlFor(slug)}>Open it as a page instead</a>
            </div>
          ) : content ? (
            <div dangerouslySetInnerHTML={{ __html: content.html }} />
          ) : (
            <div className="modal-skeleton" aria-label="Loading">
              {Array.from({ length: 9 }, (_, i) => (
                <i key={i} style={{ width: `${[92, 70, 84, 60, 96, 76, 88, 52, 80][i]}%` }} />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

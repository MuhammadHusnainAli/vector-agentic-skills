"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { REPO_URL } from "@/lib/constants";
import { ArrowRight, Close, Logo, Menu, Search } from "./icons";
import { openPalette } from "./search";

const NAV = [
  { href: "/", label: "Home" },
  { href: "/skills/", label: "Skills" },
  { href: "/categories/", label: "Categories" },
  { href: "/install/", label: "Install" },
  { href: "/contact/", label: "Contact" },
];

export type SiteStats = {
  skills: number;
  categories: number;
  subcategories: number;
  scripts: number;
  references: number;
};

/** Premium green strip above the nav: current release and index totals. */
function AnnouncementBar({ version, stats }: { version: string; stats: SiteStats }) {
  return (
    <div className="announce">
      <div className="announce-inner">
        <span className="announce-release">
          <span className="live-dot" />
          <b>{version}</b>
          <span className="hide-sm">latest release</span>
        </span>
        <span className="announce-stats">
          <span>
            <b>{stats.skills}</b> skills
          </span>
          <span>
            <b>{stats.categories}</b> categories
          </span>
          <span className="hide-md">
            <b>{stats.subcategories}</b> sub-categories
          </span>
          <span className="hide-sm">
            <b>{stats.scripts}</b> tested scripts
          </span>
          <span className="hide-md">
            <b>{stats.references}</b> reference docs
          </span>
        </span>
        <Link href="/contact/" className="announce-link hide-sm">
          Contact us <ArrowRight />
        </Link>
      </div>
    </div>
  );
}

export function Header({ version, stats }: { version: string; stats: SiteStats }) {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 24);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  const isActive = (href: string) => (href === "/" ? pathname === "/" : pathname.startsWith(href));

  return (
    <header className={`site-top${scrolled ? " scrolled" : ""}`}>
      <AnnouncementBar version={version} stats={stats} />
      <div className="site-nav">
      <div className="nav-pill">
        <Link href="/" className="brand" aria-label="Vector Agentic Skills home" onClick={() => setOpen(false)}>
          <Logo />
          <span>
            <b>Vector</b> Agentic Skills
          </span>
        </Link>
        <nav className="nav-links" aria-label="Main">
          {NAV.map((n) => (
            <Link key={n.href} href={n.href} aria-current={isActive(n.href) ? "page" : undefined}>
              {n.label}
            </Link>
          ))}
        </nav>
        <div className="nav-actions">
          <button type="button" className="nav-search" onClick={() => openPalette()} aria-label="Search skills">
            <Search />
            <span>Search</span>
            <kbd>⌘K</kbd>
          </button>
          <button type="button" className="nav-icon nav-search-sm" onClick={() => openPalette()} aria-label="Search skills">
            <Search />
          </button>
          <a
            className="nav-cta"
            href={`${REPO_URL}/blob/main/README.md#contributing`}
            target="_blank"
            rel="noopener"
          >
            Submit a skill
          </a>
          <button
            type="button"
            className="nav-icon nav-menu"
            aria-label={open ? "Close menu" : "Open menu"}
            aria-expanded={open}
            onClick={() => setOpen((o) => !o)}
          >
            {open ? <Close /> : <Menu />}
          </button>
        </div>
      </div>
      {open && (
        <nav className="nav-panel" aria-label="Mobile">
          {NAV.map((n) => (
            <Link key={n.href} href={n.href} onClick={() => setOpen(false)} aria-current={isActive(n.href) ? "page" : undefined}>
              {n.label}
              <ArrowRight />
            </Link>
          ))}
          <a href={`${REPO_URL}/blob/main/README.md#contributing`} target="_blank" rel="noopener" onClick={() => setOpen(false)}>
            Submit a skill
            <ArrowRight />
          </a>
        </nav>
      )}
      </div>
    </header>
  );
}

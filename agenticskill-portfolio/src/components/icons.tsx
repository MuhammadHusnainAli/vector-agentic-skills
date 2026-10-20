import type { SVGProps } from "react";

type P = SVGProps<SVGSVGElement>;
const base = { fill: "none", stroke: "currentColor", strokeWidth: 1.6, strokeLinecap: "round", strokeLinejoin: "round" } as const;

export const ArrowRight = (p: P) => (
  <svg viewBox="0 0 24 24" {...base} {...p}>
    <path d="M5 12h14M13 6l6 6-6 6" />
  </svg>
);
export const ArrowUpRight = (p: P) => (
  <svg viewBox="0 0 24 24" {...base} {...p}>
    <path d="M7 17 17 7M8 7h9v9" />
  </svg>
);
export const Search = (p: P) => (
  <svg viewBox="0 0 24 24" {...base} {...p}>
    <circle cx="11" cy="11" r="7" />
    <path d="m20 20-3.5-3.5" />
  </svg>
);
export const Menu = (p: P) => (
  <svg viewBox="0 0 24 24" {...base} {...p}>
    <path d="M4 7h16M4 12h16M4 17h16" />
  </svg>
);
export const Close = (p: P) => (
  <svg viewBox="0 0 24 24" {...base} {...p}>
    <path d="M6 6l12 12M18 6 6 18" />
  </svg>
);
export const FileIcon = (p: P) => (
  <svg viewBox="0 0 24 24" {...base} {...p}>
    <path d="M14 3H6v18h12V7z" />
    <path d="M14 3v4h4" />
  </svg>
);
export const CodeIcon = (p: P) => (
  <svg viewBox="0 0 24 24" {...base} {...p}>
    <path d="m8 7-5 5 5 5M16 7l5 5-5 5" />
  </svg>
);
export const Download = (p: P) => (
  <svg viewBox="0 0 24 24" {...base} {...p}>
    <path d="M12 4v11M7 10l5 5 5-5M5 20h14" />
  </svg>
);
export const GitHub = (p: P) => (
  <svg viewBox="0 0 24 24" fill="currentColor" {...p}>
    <path d="M12 .5a11.5 11.5 0 0 0-3.64 22.41c.58.1.79-.25.79-.56v-2c-3.2.7-3.88-1.37-3.88-1.37-.53-1.33-1.28-1.69-1.28-1.69-1.05-.71.08-.7.08-.7 1.16.08 1.77 1.2 1.77 1.2 1.03 1.76 2.7 1.25 3.36.96.1-.75.4-1.25.73-1.54-2.55-.29-5.24-1.28-5.24-5.68 0-1.26.45-2.28 1.19-3.09-.12-.29-.52-1.46.11-3.05 0 0 .97-.31 3.17 1.18a11 11 0 0 1 5.77 0c2.2-1.49 3.17-1.18 3.17-1.18.63 1.59.23 2.76.11 3.05.74.81 1.19 1.83 1.19 3.09 0 4.41-2.69 5.39-5.25 5.67.41.36.78 1.06.78 2.14v3.17c0 .31.21.67.8.56A11.5 11.5 0 0 0 12 .5Z" />
  </svg>
);

/**
 * Vector Agentic Skills mark: a "V" whose right stroke becomes a vector arrow,
 * starting from a skill node. `tone="light"` is for green backgrounds.
 */
export const Logo = ({ tone = "dark", ...p }: P & { tone?: "dark" | "light" }) => {
  const c = tone === "light" ? ["#c3d3bc", "#ffffff", "#9bb294"] : ["#9bb294", "#2f3d32", "#4f6552"];
  return (
    <svg viewBox="0 0 32 32" fill="none" strokeWidth={4.4} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...p}>
      <path d="M6.5 8.5 14.5 24" stroke={c[0]} />
      <path d="M14.5 24 25 7" stroke={c[1]} />
      <path d="M18.6 6.4h7v7" stroke={c[1]} />
      <circle cx="6.5" cy="8.5" r="3.6" fill={c[2]} stroke="none" />
    </svg>
  );
};

export const Database = (p: P) => (
  <svg viewBox="0 0 24 24" {...base} {...p}>
    <ellipse cx="12" cy="5.5" rx="7.5" ry="3" />
    <path d="M4.5 5.5v13c0 1.7 3.4 3 7.5 3s7.5-1.3 7.5-3v-13M4.5 12c0 1.7 3.4 3 7.5 3s7.5-1.3 7.5-3" />
  </svg>
);
export const Sheet = (p: P) => (
  <svg viewBox="0 0 24 24" {...base} {...p}>
    <rect x="3.5" y="3.5" width="17" height="17" rx="2.5" />
    <path d="M3.5 9h17M3.5 14.5h17M9 9v11.5" />
  </svg>
);
export const Folder = (p: P) => (
  <svg viewBox="0 0 24 24" {...base} {...p}>
    <path d="M3.5 7.5a2 2 0 0 1 2-2h4l2 2.5h7a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-13a2 2 0 0 1-2-2z" />
  </svg>
);
export const Book = (p: P) => (
  <svg viewBox="0 0 24 24" {...base} {...p}>
    <path d="M4.5 5.5A2 2 0 0 1 6.5 3.5h13v15h-13a2 2 0 0 0-2 2zM4.5 20.5a2 2 0 0 0 2 2h13v-4" />
  </svg>
);
export const TerminalIcon = (p: P) => (
  <svg viewBox="0 0 24 24" {...base} {...p}>
    <rect x="2.5" y="4" width="19" height="16" rx="3" />
    <path d="m7 9.5 3 2.5-3 2.5M12.5 15h4.5" />
  </svg>
);

/** Icon for a sub-category slug. */
export function SubcategoryIcon({ slug, ...p }: P & { slug: string }) {
  if (slug === "sql") return <Database {...p} />;
  if (slug === "excel") return <Sheet {...p} />;
  return <Folder {...p} />;
}

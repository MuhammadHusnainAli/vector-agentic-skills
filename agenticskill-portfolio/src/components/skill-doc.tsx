import Link from "next/link";
import type { TocItem } from "@/lib/markdown";
import { REPO_URL, formatDate } from "@/lib/site";
import { getCategory, getSubcategory, type Skill } from "@/lib/skills";
import { FileModal } from "./file-modal";
import { ArrowRight, CodeIcon, Download, FileIcon, GitHub } from "./icons";
import { InstallTabs } from "./install-tabs";

/** Shared page frame for a skill's SKILL.md and its reference/script files. */
export function SkillDoc({
  skill,
  current,
  html,
  toc,
  isSource,
}: {
  skill: Skill;
  /** Slug of the file being shown, or null for SKILL.md. */
  current: string | null;
  html: string;
  toc: TocItem[];
  isSource?: boolean;
}) {
  const category = getCategory(skill.category)!;
  const sub = getSubcategory(skill.category, skill.subcategory)!;
  const subHref = `/categories/${category.slug}/${sub.slug}/`;
  const file = current ? skill.files.find((f) => f.slug === current)! : null;
  const pages = [{ slug: null as string | null, label: "SKILL.md" }, ...skill.files.map((f) => ({ slug: f.slug, label: f.file }))];
  const idx = pages.findIndex((p) => p.slug === current);
  const prev = pages[idx - 1];
  const next = pages[idx + 1];
  const href = (slug: string | null) => `/skills/${skill.name}/${slug ? `${slug}/` : ""}`;
  const related = sub.skills.filter((s) => s.name !== skill.name).slice(0, 6);
  const rawPath = `/raw/${skill.dir}/${file ? file.file : "SKILL.md"}`;
  const refCount = skill.files.filter((f) => f.kind === "reference").length;
  const scriptCount = skill.files.filter((f) => f.kind === "script").length;

  return (
    <>
      <div className="page-head">
        <div className="container">
          <nav className="crumbs" aria-label="Breadcrumb">
            <Link href="/">Home</Link> / <Link href="/skills/">Skills</Link> /{" "}
            <Link href={`/categories/${category.slug}/`}>{category.title}</Link> /{" "}
            <Link href={subHref}>{sub.title}</Link> /{" "}
            {file ? (
              <>
                <Link href={href(null)}>{skill.name}</Link> / <span>{file.file}</span>
              </>
            ) : (
              <span>{skill.name}</span>
            )}
          </nav>
          {file ? (
            <h1 className={file.kind === "script" ? "mono-title" : undefined}>{file.title}</h1>
          ) : (
            <h1 className="mono-title">{skill.name}</h1>
          )}
          <p className="sub">
            {file ? (
              <>
                {file.kind === "script" ? "Helper script" : "Reference"} for{" "}
                <Link href={href(null)} style={{ textDecoration: "underline" }}>
                  {skill.name}
                </Link>{" "}
                · {file.lines} lines
              </>
            ) : (
              skill.description
            )}
          </p>
          <div className="meta-row">
            <Link href={subHref} className="badge solid">
              {category.title} / {sub.title}
            </Link>
            <span className="badge">v{skill.version}</span>
            <span className="badge">Updated {formatDate(skill.updated)}</span>
            {refCount > 0 && (
              <span className="badge">
                {refCount} {refCount === 1 ? "reference" : "references"}
              </span>
            )}
            {scriptCount > 0 && (
              <span className="badge accent">
                {scriptCount} {scriptCount === 1 ? "script" : "scripts"}
              </span>
            )}
          </div>
        </div>
      </div>

      {!file && (
        <FileModal
          skill={skill.name}
          dir={skill.dir}
          files={skill.files.map((f) => ({ slug: f.slug, file: f.file, kind: f.kind, lines: f.lines }))}
        />
      )}
      <div className="container doc-layout">
        <aside className="doc-aside first">
          {!file && <InstallTabs skill={skill.name} subcategory={skill.subcategory} />}

          <div className="aside-box">
            <h4 className="label">Files</h4>
            <ul className="file-list">
              {pages.map((p) => {
                const f = skill.files.find((x) => x.slug === p.slug);
                return (
                  <li key={p.label}>
                    <Link href={href(p.slug)} aria-current={p.slug === current ? "page" : undefined}>
                      {f?.kind === "script" ? <CodeIcon /> : <FileIcon />}
                      {p.label}
                      {f && <small>{f.lines}</small>}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>

          {toc.length > 0 && (
            <div className="aside-box toc-box">
              <h4 className="label">On this page</h4>
              <ul className="toc">
                {toc.map((t) => (
                  <li key={t.id} className={`d${t.depth}`}>
                    <a href={`#${t.id}`}>{t.text}</a>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="aside-box">
            <h4 className="label">Download</h4>
            <div className="dl-links">
              <a href={`/dl/${skill.name}.tar.gz`} download>
                {skill.name}.tar.gz <Download width={16} height={16} />
              </a>
              <a href={rawPath} target="_blank" rel="noopener">
                Raw {file ? file.file.split("/").pop() : "SKILL.md"} <ArrowRight width={16} height={16} />
              </a>
              <a href={`${REPO_URL}/tree/main/${skill.dir}`} target="_blank" rel="noopener">
                View on GitHub <GitHub width={16} height={16} />
              </a>
            </div>
          </div>
        </aside>

        <article style={{ minWidth: 0 }}>
          {isSource ? (
            <figure className="code source">
              <figcaption>
                <span>{file?.file}</span>
                <button type="button" className="copy" data-copy="">
                  Copy
                </button>
              </figcaption>
              <div dangerouslySetInnerHTML={{ __html: html }} />
            </figure>
          ) : (
            <div className="prose" dangerouslySetInnerHTML={{ __html: html }} />
          )}

          <nav className="pager" aria-label="Skill files">
            {prev ? (
              <Link href={href(prev.slug)}>
                <span className="label">← Previous</span>
                <b>{prev.label}</b>
              </Link>
            ) : (
              <span />
            )}
            {next && (
              <Link href={href(next.slug)} className="next">
                <span className="label">Next →</span>
                <b>{next.label}</b>
              </Link>
            )}
          </nav>

          {related.length > 0 && (
            <section style={{ marginTop: 64 }}>
              <span className="label">More in {sub.title}</span>
              <div className="cards" style={{ marginTop: 16 }}>
                {related.map((r) => (
                  <Link key={r.name} href={`/skills/${r.name}/`} className="card">
                    <h3>{r.name}</h3>
                    <p>{r.summary}</p>
                  </Link>
                ))}
              </div>
            </section>
          )}
        </article>
      </div>
    </>
  );
}

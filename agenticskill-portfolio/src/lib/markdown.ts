import "server-only";
import path from "node:path";
import { Marked, type Tokens } from "marked";
import { createHighlighter, type Highlighter } from "shiki";
import { REPO_URL } from "./site";

const LANGS = ["sql", "bash", "python", "vb", "json", "yaml", "markdown", "typescript"] as const;
const ALIASES: Record<string, string> = { vba: "vb", sh: "bash", shell: "bash", py: "python", ts: "typescript", md: "markdown", yml: "yaml" };

let highlighter: Promise<Highlighter> | null = null;
function getHighlighter() {
  highlighter ??= createHighlighter({ themes: ["github-light"], langs: [...LANGS] });
  return highlighter;
}

export type TocItem = { id: string; text: string; depth: number };

function slugify(text: string): string {
  return text
    .toLowerCase()
    .replace(/<[^>]+>/g, "")
    .replace(/[`*_]/g, "")
    .replace(/[^a-z0-9\s-]/g, "")
    .trim()
    .replace(/\s+/g, "-");
}

/**
 * Map a relative Markdown link inside a skill to a site route.
 * `fromFile` is the repo-relative path of the file containing the link.
 */
function resolveLink(href: string, fromFile: string): string {
  if (/^([a-z]+:|#|\/)/i.test(href)) return href;
  const [target, hash] = href.split("#");
  const repoPath = path.posix.normalize(path.posix.join(path.posix.dirname(fromFile), target));
  const parts = repoPath.split("/");
  // skills/<category>/<subcategory>/<skill>/SKILL.md  or  .../<skill>/(references|scripts)/<file>
  if (parts[0] === "skills" && parts.length >= 5) {
    const skill = parts[3];
    const suffix = hash ? `#${hash}` : "";
    if (parts.length === 5 && parts[4] === "SKILL.md") return `/skills/${skill}/${suffix}`;
    const base = parts[parts.length - 1];
    const slug = base.endsWith(".md") ? base.slice(0, -3).toLowerCase() : base;
    return `/skills/${skill}/${slug}/${suffix}`;
  }
  return `${REPO_URL}/blob/main/${repoPath}${hash ? `#${hash}` : ""}`;
}

function decodeEntities(s: string) {
  return s
    .replace(/&#39;/g, "'")
    .replace(/&quot;/g, '"')
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&amp;/g, "&");
}

function escapeHtml(s: string) {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

/** Render Markdown to HTML with highlighted code blocks and a table of contents. */
export async function renderMarkdown(md: string, fromFile: string): Promise<{ html: string; toc: TocItem[] }> {
  const hl = await getHighlighter();
  const toc: TocItem[] = [];
  const seen = new Map<string, number>();

  const marked = new Marked({
    gfm: true,
    renderer: {
      heading({ tokens, depth }: Tokens.Heading) {
        const text = this.parser.parseInline(tokens);
        let id = slugify(decodeEntities(text)) || "section";
        const n = seen.get(id) ?? 0;
        seen.set(id, n + 1);
        if (n) id = `${id}-${n}`;
        if (depth === 2 || depth === 3) toc.push({ id, text: decodeEntities(text.replace(/<[^>]+>/g, "")), depth });
        if (depth === 1) return ""; // the page header already shows the title
        return `<h${depth} id="${id}"><a class="anchor" href="#${id}" aria-hidden="true">#</a>${text}</h${depth}>`;
      },
      link({ href, title, tokens }: Tokens.Link) {
        const text = this.parser.parseInline(tokens);
        const url = resolveLink(href, fromFile);
        const external = /^https?:/.test(url);
        return `<a href="${url}"${title ? ` title="${title}"` : ""}${external ? ' target="_blank" rel="noopener"' : ""}>${text}</a>`;
      },
      code({ text, lang }: Tokens.Code) {
        const raw = (lang ?? "").trim().toLowerCase();
        const language = ALIASES[raw] ?? raw;
        const label = raw || (text.trimStart().startsWith("=") ? "excel" : "text");
        const body = (LANGS as readonly string[]).includes(language)
          ? hl.codeToHtml(text, {
              lang: language,
              theme: "github-light",
            })
          : `<pre class="shiki plain"><code>${escapeHtml(text)}</code></pre>`;
        return `<figure class="code"><figcaption><span>${label}</span><button type="button" class="copy" data-copy>Copy</button></figcaption>${body}</figure>`;
      },
      table(token: Tokens.Table) {
        const head = token.header.map((c) => `<th>${this.parser.parseInline(c.tokens)}</th>`).join("");
        const rows = token.rows
          .map((r) => `<tr>${r.map((c) => `<td>${this.parser.parseInline(c.tokens)}</td>`).join("")}</tr>`)
          .join("");
        return `<div class="table-wrap"><table><thead><tr>${head}</tr></thead><tbody>${rows}</tbody></table></div>`;
      },
    },
  });

  const html = await marked.parse(md);
  return { html, toc };
}

/** Render a source file (e.g. a Python script) as a highlighted block. */
export async function renderSource(code: string, file: string): Promise<string> {
  const ext = path.extname(file).slice(1);
  const lang = ALIASES[ext] ?? ext;
  const hl = await getHighlighter();
  if (!(LANGS as readonly string[]).includes(lang)) return `<pre class="shiki plain"><code>${escapeHtml(code)}</code></pre>`;
  return hl.codeToHtml(code, { lang, theme: "github-light" });
}

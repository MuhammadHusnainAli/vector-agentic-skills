import type { Metadata } from "next";
import Link from "next/link";
import { CopyCommand } from "@/components/install-tabs";
import { MARKETPLACE, REPO, SITE_URL } from "@/lib/site";
import { getCategories } from "@/lib/skills";

export const metadata: Metadata = {
  title: "Install guide",
  description: "Install Agent Skills with npx skills, the Claude Code plugin marketplace, or a curl one-liner.",
  alternates: { canonical: "/install/" },
};

const TOC = [
  ["npx", "npx skills (any agent)"],
  ["claude-code", "Claude Code plugin"],
  ["curl", "curl one-liner"],
  ["where", "Where skills live"],
  ["versions", "Versions"],
];

export default function InstallPage() {
  const categories = getCategories();
  return (
    <>
      <div className="page-head">
        <div className="container">
          <nav className="crumbs" aria-label="Breadcrumb">
            <Link href="/">Home</Link> / <span>Install</span>
          </nav>
          <h1 >
            Install <span className="hl">guide</span>
          </h1>
          <p className="sub">
            Three ways to get a skill into your agent. Pick one; they all produce the same folder with a SKILL.md
            inside.
          </p>
        </div>
      </div>

      <div className="container doc-layout">
        <aside className="doc-aside first">
          <div className="aside-box">
            <h4 className="label">On this page</h4>
            <ul className="toc">
              {TOC.map(([id, label]) => (
                <li key={id} className="d2">
                  <a href={`#${id}`}>{label}</a>
                </li>
              ))}
            </ul>
          </div>
        </aside>

        <article className="prose">
          <h2 id="npx">npx skills (any agent)</h2>
          <p>
            The <a href="https://github.com/vercel-labs/skills">skills CLI</a> installs into Claude Code, Codex,
            Cursor, Gemini CLI, OpenCode and 70+ other agents. Run it from your project, or add <code>-g</code> to
            install for your user.
          </p>
          <CopyCommand command={`npx skills add ${SITE_URL} --skill sql-query-writer`} />
          <p style={{ marginTop: 16 }}>List everything in the repo, or install all skills at once:</p>
          <CopyCommand command={`npx skills add ${SITE_URL} --list`} />
          <div style={{ height: 10 }} />
          <CopyCommand command={`npx skills add ${SITE_URL} --all`} />

          <h2 id="claude-code">Claude Code plugin</h2>
          <p>Each sub-category is a plugin in the {MARKETPLACE} marketplace. Inside Claude Code:</p>
          <CopyCommand
            command={`/plugin marketplace add ${REPO}\n${categories
              .flatMap((c) => c.subcategories)
              .map((s) => `/plugin install ${s.slug}-skills@${MARKETPLACE}`)
              .join("\n")}`}
          />
          <p style={{ marginTop: 16 }}>
            Installed skills load automatically when your request matches their description. You can also call one
            directly, for example <code>/sql-query-writer</code>.
          </p>

          <h2 id="curl">curl one-liner</h2>
          <p>No Node or git needed. Every skill is published as a tarball on this site:</p>
          <CopyCommand
            command={`mkdir -p ~/.claude/skills && curl -fsSL ${SITE_URL}/dl/sql-query-writer.tar.gz | tar -xz -C ~/.claude/skills`}
          />
          <p style={{ marginTop: 16 }}>A whole sub-category (here SQL), or everything at once:</p>
          <CopyCommand
            command={`mkdir -p ~/.claude/skills && curl -fsSL ${SITE_URL}/dl/sql-skills.tar.gz | tar -xz -C ~/.claude/skills`}
          />
          <div style={{ height: 10 }} />
          <CopyCommand
            command={`mkdir -p ~/.claude/skills && curl -fsSL ${SITE_URL}/dl/all-skills.tar.gz | tar -xz -C ~/.claude/skills`}
          />

          <h2 id="where">Where skills live</h2>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Scope</th>
                  <th>Claude Code path</th>
                  <th>Use for</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>Personal</td>
                  <td>
                    <code>~/.claude/skills/&lt;name&gt;/</code>
                  </td>
                  <td>Available in every project</td>
                </tr>
                <tr>
                  <td>Project</td>
                  <td>
                    <code>.claude/skills/&lt;name&gt;/</code>
                  </td>
                  <td>Shared with your team through git</td>
                </tr>
                <tr>
                  <td>Plugin</td>
                  <td>Managed by /plugin</td>
                  <td>Install and update whole categories</td>
                </tr>
              </tbody>
            </table>
          </div>
          <p>Restart your agent session after installing so it picks up new skills.</p>

          <h2 id="versions">Versions</h2>
          <p>
            The version in the top bar is the site release. Every push to <code>main</code> deploys a new release and
            bumps the last number (v0.1.0, v0.1.1, ...). The first two numbers come from the <code>VERSION</code> file
            in the repository and are changed by hand for bigger releases. Each skill also carries its own version in
            its SKILL.md frontmatter.
          </p>
          <p>
            Machine-readable index: <a href="/catalog.json">/catalog.json</a> · Sitemap:{" "}
            <a href="/sitemap.xml">/sitemap.xml</a>
          </p>
        </article>
      </div>
    </>
  );
}

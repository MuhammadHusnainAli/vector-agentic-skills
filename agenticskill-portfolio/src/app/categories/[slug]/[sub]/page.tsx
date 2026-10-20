import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowUpRight } from "@/components/icons";
import { CopyCommand } from "@/components/install-tabs";
import { MARKETPLACE, REPO, SITE_URL } from "@/lib/site";
import { getCategory, getSubcategories, getSubcategory } from "@/lib/skills";

export const dynamicParams = false;

export function generateStaticParams() {
  return getSubcategories().map((s) => ({ slug: s.category, sub: s.slug }));
}

export async function generateMetadata({ params }: PageProps<"/categories/[slug]/[sub]">): Promise<Metadata> {
  const { slug, sub } = await params;
  const s = getSubcategory(slug, sub);
  if (!s) return {};
  return {
    title: `${s.title} skills`,
    description: `${s.skills.length} ${s.title} skills for AI agents: ${s.skills.map((k) => k.name).join(", ")}. ${s.description}`,
    alternates: { canonical: `/categories/${slug}/${sub}/` },
  };
}

export default async function SubcategoryPage({ params }: PageProps<"/categories/[slug]/[sub]">) {
  const { slug, sub } = await params;
  const c = getCategory(slug);
  const s = getSubcategory(slug, sub);
  if (!c || !s) notFound();
  const scripts = s.skills.reduce((n, k) => n + k.files.filter((f) => f.kind === "script").length, 0);
  return (
    <>
      <div className="page-head">
        <div className="container">
          <nav className="crumbs" aria-label="Breadcrumb">
            <Link href="/">Home</Link> / <Link href="/categories/">Categories</Link> /{" "}
            <Link href={`/categories/${c.slug}/`}>{c.title}</Link> / <span>{s.title}</span>
          </nav>
          <h1 >
            {s.title} <span className="hl">skills</span>
          </h1>
          <p className="sub">
            {s.description}
          </p>
          <div className="meta-row">
            <span className="badge solid">{s.skills.length} skills</span>
            <span className="badge accent">{scripts} scripts</span>
            <span className="badge">plugin: {s.slug}-skills</span>
          </div>
        </div>
      </div>
      <div className="container" style={{ paddingTop: 48, paddingBottom: 96 }}>
        <div className="tabs" style={{ marginBottom: 40 }}>
          <div className="tabpanel">
            <p>Install every {s.title} skill at once in Claude Code:</p>
            <CopyCommand command={`/plugin marketplace add ${REPO}\n/plugin install ${s.slug}-skills@${MARKETPLACE}`} />
            <p style={{ margin: "16px 0 14px" }}>With npx skills, for any agent:</p>
            <CopyCommand command={`npx skills add ${SITE_URL} ${s.skills.map((k) => `--skill ${k.name}`).join(" ")}`} />
            <p style={{ margin: "16px 0 14px" }}>Or download them all:</p>
            <CopyCommand
              command={`mkdir -p ~/.claude/skills && curl -fsSL ${SITE_URL}/dl/${s.slug}-skills.tar.gz | tar -xz -C ~/.claude/skills`}
            />
          </div>
        </div>
        <div className="cards">
          {s.skills.map((k) => (
            <Link key={k.name} href={`/skills/${k.name}/`} className="card">
              <div className="top">
                <span className="badge">v{k.version}</span>
                <ArrowUpRight width={16} height={16} />
              </div>
              <h3>{k.name}</h3>
              <p>{k.summary}</p>
              <div className="meta">
                <span className="badge">SKILL.md</span>
                {k.files
                  .filter((f) => f.kind === "script")
                  .map((f) => (
                    <span key={f.file} className="badge accent">
                      {f.file.split("/").pop()}
                    </span>
                  ))}
              </div>
            </Link>
          ))}
        </div>
      </div>
    </>
  );
}

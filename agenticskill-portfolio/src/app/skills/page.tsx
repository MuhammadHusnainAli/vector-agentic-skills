import type { Metadata } from "next";
import Link from "next/link";
import { SkillExplorer } from "@/components/skill-explorer";
import { getCategories, searchIndex, stats } from "@/lib/skills";

export const metadata: Metadata = {
  title: "All skills",
  description: "Search and filter every Agent Skill in the index by name, topic, function or category.",
  alternates: { canonical: "/skills/" },
};

export default function SkillsPage() {
  const s = stats();
  const categories = getCategories().map((c) => ({
    slug: c.slug,
    title: c.title,
    count: c.skills.length,
    subcategories: c.subcategories.map((s) => ({ slug: s.slug, title: s.title, count: s.skills.length })),
  }));
  return (
    <>
      <div className="page-head">
        <div className="container">
          <nav className="crumbs" aria-label="Breadcrumb">
            <Link href="/">Home</Link> / <span>Skills</span>
          </nav>
          <h1 >
            All <span className="hl">skills</span>
          </h1>
          <p className="sub">
            {s.skills} skills, {s.references} reference docs and {s.scripts} helper scripts. Search matches names,
            descriptions, section headings and reference titles.
          </p>
        </div>
      </div>
      <div className="container" style={{ paddingBottom: 96 }}>
        <SkillExplorer index={searchIndex()} categories={categories} />
      </div>
    </>
  );
}

import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getCategories, getCategory } from "@/lib/skills";
import { SubcategoryCards } from "@/components/subcategory-cards";

export const dynamicParams = false;

export function generateStaticParams() {
  return getCategories().map((c) => ({ slug: c.slug }));
}

export async function generateMetadata({ params }: PageProps<"/categories/[slug]">): Promise<Metadata> {
  const { slug } = await params;
  const c = getCategory(slug);
  if (!c) return {};
  return {
    title: `${c.title} skills`,
    description: `${c.description} Sub-categories: ${c.subcategories.map((s) => s.title).join(", ")}.`,
    alternates: { canonical: `/categories/${c.slug}/` },
  };
}

export default async function CategoryPage({ params }: PageProps<"/categories/[slug]">) {
  const { slug } = await params;
  const c = getCategory(slug);
  if (!c) notFound();
  return (
    <>
      <div className="page-head">
        <div className="container">
          <nav className="crumbs" aria-label="Breadcrumb">
            <Link href="/">Home</Link> / <Link href="/categories/">Categories</Link> / <span>{c.title}</span>
          </nav>
          <h1 >
            {c.title} <span className="hl">skills</span>
          </h1>
          <p className="sub">
            {c.description}
          </p>
          <div className="meta-row">
            <span className="badge solid">{c.skills.length} skills</span>
            {c.subcategories.map((s) => (
              <Link key={s.slug} href={`/categories/${c.slug}/${s.slug}/`} className="badge">
                {s.title} · {s.skills.length}
              </Link>
            ))}
          </div>
        </div>
      </div>
      <div className="container" style={{ paddingTop: 48, paddingBottom: 96 }}>
        <SubcategoryCards subcategories={c.subcategories} categoryTitles={{ [c.slug]: c.title }} />
      </div>
    </>
  );
}

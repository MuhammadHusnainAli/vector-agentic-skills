import type { Metadata } from "next";
import Link from "next/link";
import { getCategories } from "@/lib/skills";
import { SubcategoryCards } from "@/components/subcategory-cards";

export const metadata: Metadata = {
  title: "Categories",
  description: "Agent Skills grouped by category and sub-category: Programming / SQL, Productivity / Excel and more.",
  alternates: { canonical: "/categories/" },
};

export default function CategoriesPage() {
  const categories = getCategories();
  const subs = categories.reduce((n, c) => n + c.subcategories.length, 0);
  return (
    <>
      <div className="page-head">
        <div className="container">
          <nav className="crumbs" aria-label="Breadcrumb">
            <Link href="/">Home</Link> / <span>Categories</span>
          </nav>
          <h1 >
            Browse by <span className="hl">category</span>
          </h1>
          <p className="sub">
            {categories.length} categories and {subs} sub-categories. New ones appear here automatically when a folder
            is added under skills/ in the repository.
          </p>
        </div>
      </div>
      <div className="container" style={{ paddingTop: 48, paddingBottom: 96 }}>
        {categories.map((c) => (
          <section key={c.slug} className="cat-block">
            <div className="cat-heading">
              <div>
                <h2>{c.title}</h2>
                <p>{c.description}</p>
              </div>
              <Link href={`/categories/${c.slug}/`} className="text-link">
                {c.skills.length} skills <span aria-hidden="true">→</span>
              </Link>
            </div>
            <SubcategoryCards subcategories={c.subcategories} categoryTitles={{ [c.slug]: c.title }} />
          </section>
        ))}
      </div>
    </>
  );
}

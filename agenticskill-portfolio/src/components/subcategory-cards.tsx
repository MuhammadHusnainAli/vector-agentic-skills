import Link from "next/link";
import type { Subcategory } from "@/lib/skills";
import { ArrowRight, SubcategoryIcon } from "./icons";

/** Mint cards, one per sub-category, listing every skill inside it. */
export function SubcategoryCards({ subcategories, categoryTitles }: {
  subcategories: Subcategory[];
  categoryTitles: Record<string, string>;
}) {
  return (
    <div className="sub-grid">
      {subcategories.map((sub) => {
        const scripts = sub.skills.reduce((n, k) => n + k.files.filter((f) => f.kind === "script").length, 0);
        return (
          <article key={`${sub.category}/${sub.slug}`} className="sub-card">
            <div className="sub-card-head">
              <span className="sub-icon">
                <SubcategoryIcon slug={sub.slug} />
              </span>
              <span className="pill">{categoryTitles[sub.category]}</span>
            </div>
            <h3>
              <Link href={`/categories/${sub.category}/${sub.slug}/`}>{sub.title}</Link>
            </h3>
            <p>{sub.description}</p>
            <div className="sub-meta">
              <span>
                <b>{sub.skills.length}</b> skills
              </span>
              <span>
                <b>{scripts}</b> tested scripts
              </span>
            </div>
            <ul className="skill-chips">
              {sub.skills.map((k) => (
                <li key={k.name}>
                  <Link href={`/skills/${k.name}/`}>{k.name}</Link>
                </li>
              ))}
            </ul>
            <Link href={`/categories/${sub.category}/${sub.slug}/`} className="text-link">
              Explore {sub.title} skills <ArrowRight />
            </Link>
          </article>
        );
      })}
    </div>
  );
}

import type { MetadataRoute } from "next";
import { buildDate, siteUrl } from "@/lib/site";
import { getCategories, getSkills, getSubcategories } from "@/lib/skills";

// Generated on every build from the skills folder, so new skills are indexed
// as soon as they are deployed.
export const dynamic = "force-static";

export default function sitemap(): MetadataRoute.Sitemap {
  const skills = getSkills();
  const latest = skills.reduce((d, s) => (s.updated > d ? s.updated : d), "");
  const now = buildDate();
  const base = siteUrl();
  const url = (p: string) => `${base}${p}`;

  return [
    { url: url("/"), lastModified: latest || now, changeFrequency: "daily", priority: 1 },
    { url: url("/skills/"), lastModified: latest || now, changeFrequency: "daily", priority: 0.9 },
    { url: url("/categories/"), lastModified: latest || now, changeFrequency: "weekly", priority: 0.8 },
    { url: url("/install/"), lastModified: now, changeFrequency: "monthly", priority: 0.6 },
    { url: url("/contact/"), lastModified: now, changeFrequency: "yearly", priority: 0.5 },
    ...getCategories().map((c) => ({
      url: url(`/categories/${c.slug}/`),
      lastModified: c.skills.reduce((d, s) => (s.updated > d ? s.updated : d), ""),
      changeFrequency: "weekly" as const,
      priority: 0.8,
    })),
    ...getSubcategories().map((s) => ({
      url: url(`/categories/${s.category}/${s.slug}/`),
      lastModified: s.skills.reduce((d, k) => (k.updated > d ? k.updated : d), ""),
      changeFrequency: "weekly" as const,
      priority: 0.85,
    })),
    ...skills.flatMap((s) => [
      { url: url(`/skills/${s.name}/`), lastModified: s.updated, changeFrequency: "weekly" as const, priority: 0.9 },
      ...s.files.map((f) => ({
        url: url(`/skills/${s.name}/${f.slug}/`),
        lastModified: s.updated,
        changeFrequency: "monthly" as const,
        priority: 0.6,
      })),
    ]),
  ];
}

import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { SkillDoc } from "@/components/skill-doc";
import { renderMarkdown, renderSource } from "@/lib/markdown";
import { getSkill, getSkills } from "@/lib/skills";

export const dynamicParams = false;

export function generateStaticParams() {
  return getSkills().flatMap((s) => s.files.map((f) => ({ name: s.name, file: f.slug })));
}

function lookup(name: string, slug: string) {
  const skill = getSkill(name);
  const file = skill?.files.find((f) => f.slug === slug);
  return skill && file ? { skill, file } : null;
}

export async function generateMetadata({ params }: PageProps<"/skills/[name]/[file]">): Promise<Metadata> {
  const { name, file: slug } = await params;
  const found = lookup(name, slug);
  if (!found) return {};
  const { skill, file } = found;
  return {
    title: `${file.title} · ${skill.name}`,
    description: `${file.kind === "script" ? "Helper script" : "Reference"} for the ${skill.name} skill: ${skill.summary}`,
    alternates: { canonical: `/skills/${skill.name}/${file.slug}/` },
  };
}

export default async function SkillFilePage({ params }: PageProps<"/skills/[name]/[file]">) {
  const { name, file: slug } = await params;
  const found = lookup(name, slug);
  if (!found) notFound();
  const { skill, file } = found;

  if (file.file.endsWith(".md")) {
    const { html, toc } = await renderMarkdown(file.content, `${skill.dir}/${file.file}`);
    return <SkillDoc skill={skill} current={file.slug} html={html} toc={toc} />;
  }
  const html = await renderSource(file.content, file.file);
  return <SkillDoc skill={skill} current={file.slug} html={html} toc={[]} isSource />;
}

import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { SkillDoc } from "@/components/skill-doc";
import { renderMarkdown } from "@/lib/markdown";
import { getSkill, getSkills } from "@/lib/skills";

export const dynamicParams = false;

export function generateStaticParams() {
  return getSkills().map((s) => ({ name: s.name }));
}

export async function generateMetadata({ params }: PageProps<"/skills/[name]">): Promise<Metadata> {
  const { name } = await params;
  const skill = getSkill(name);
  if (!skill) return {};
  return {
    title: `${skill.name} — ${skill.title}`,
    description: skill.description,
    alternates: { canonical: `/skills/${skill.name}/` },
    openGraph: { title: skill.name, description: skill.summary, url: `/skills/${skill.name}/`, type: "article" },
  };
}

export default async function SkillPage({ params }: PageProps<"/skills/[name]">) {
  const { name } = await params;
  const skill = getSkill(name);
  if (!skill) notFound();
  const { html, toc } = await renderMarkdown(skill.body, `${skill.dir}/SKILL.md`);
  return <SkillDoc skill={skill} current={null} html={html} toc={toc} />;
}

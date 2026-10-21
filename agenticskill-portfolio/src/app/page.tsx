import Link from "next/link";
import { ContactForm } from "@/components/contact-form";
import { HeroSearch } from "@/components/home-widgets";
import { ArrowRight, Book, FileIcon, TerminalIcon } from "@/components/icons";
import { InstallTabs } from "@/components/install-tabs";
import { SubcategoryCards } from "@/components/subcategory-cards";
import { Terminal } from "@/components/terminal";
import { AGENTS, CONTACT_EMAIL, REPO_URL } from "@/lib/site";
import { getCategories, getSkills, getSubcategories, searchIndex, stats } from "@/lib/skills";

const ANATOMY = [
  {
    icon: FileIcon,
    title: "SKILL.md",
    text: "Frontmatter tells your agent when to load the skill. The body gives it a workflow, checklists and the output format to follow.",
  },
  {
    icon: Book,
    title: "references/",
    text: "Long-form examples and reference tables, loaded only when the task needs them, so they cost no context otherwise.",
  },
  {
    icon: TerminalIcon,
    title: "scripts/",
    text: "Dependency-free helpers that analyse, generate or verify, so answers are checked rather than guessed. Every one is tested in CI.",
  },
];

export default function Home() {
  const s = stats();
  const skills = getSkills();
  const categoryTitles = Object.fromEntries(getCategories().map((c) => [c.slug, c.title]));
  const demo = ["sql-query-writer", "excel-formulas", "sql-optimizer"]
    .map((n) => skills.find((k) => k.name === n))
    .filter((k) => k !== undefined)
    .map((k) => ({
      name: k.name,
      category: k.subcategory,
      count: skills.filter((x) => x.subcategory === k.subcategory).length,
    }));

  return (
    <>
      <section className="hero">
        <div className="container hero-inner">
          <h1 className="hero-title">
            Expert skills for every agent.
            <span className="serif">Install in one command.</span>
          </h1>
          <p className="hero-sub">
            Open-source Agent Skills for {AGENTS.slice(0, 4).join(", ")} and every agent that reads SKILL.md. Each
            one ships with references and tested scripts.
          </p>
          <div>
            <HeroSearch index={searchIndex()} />
          </div>
          <div className="hero-cta">
            <Link href="/skills/" className="btn btn-cream">
              Browse all skills <ArrowRight />
            </Link>
            <Link href="/install/" className="btn btn-ghost">
              Install guide
            </Link>
          </div>
          <div className="hero-stats">
            <div>
              <b>
                {s.skills}
              </b>
              <span>skills</span>
            </div>
            <div>
              <b>
                {s.scripts}
              </b>
              <span>tested scripts</span>
            </div>
            <div>
              <b>
                {s.references}
              </b>
              <span>reference docs</span>
            </div>
            <div>
              <b>
                {Math.round(s.lines / 1000)}k
              </b>
              <span>lines of guidance</span>
            </div>
          </div>
        </div>
      </section>

      <section className="section" id="categories">
        <div className="container">
          <div className="section-head center">
            <span className="eyebrow">Categories</span>
            <h2>
              Browse by <span className="hl">category</span>
            </h2>
            <p>Skills are grouped by domain, then by tool. Open a sub-category to see the skills inside it.</p>
          </div>
          <SubcategoryCards subcategories={getSubcategories()} categoryTitles={categoryTitles} showSkills={false} />
        </div>
      </section>

      <section className="section alt">
        <div className="container">
          <div className="section-head center">
            <span className="eyebrow">Anatomy</span>
            <h2>
              What ships in <span className="hl">every skill</span>
            </h2>
            <p>The same three parts, every time. Your agent reads only what the task needs.</p>
          </div>
          <div className="feature-grid">
            {ANATOMY.map(({ icon: Icon, title, text }) => (
              <div key={title} className="feature">
                <span className="feature-icon">
                  <Icon />
                </span>
                <h3>{title}</h3>
                <p>{text}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="section" id="install">
        <div className="container">
          <div className="section-head center">
            <span className="eyebrow">Install</span>
            <h2>
              One command, <span className="hl">any agent</span>
            </h2>
            <p>Use npx skills, the Claude Code plugin marketplace, curl or git. Every skill page has its own commands.</p>
          </div>
          <div className="install-grid">
            <div>
              <InstallTabs skill="sql-query-writer" subcategory="sql" />
            </div>
            <div>
              <Terminal skills={demo} />
            </div>
          </div>
        </div>
      </section>

      <section className="section alt" id="contact">
        <div className="container contact-grid">
          <div className="contact-panel">
            <span className="eyebrow on-green">Contact</span>
            <h2>
              Talk to the team.
              <span className="serif">We read every message.</span>
            </h2>
            <p>
              Ask a question, request a skill for your stack, or tell us how you use the index. We usually reply within
              two working days.
            </p>
            <ul className="contact-points">
              <li>
                <span>Email</span>
                <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>
              </li>
              <li>
                <span>Contribute</span>
                <a href={`${REPO_URL}/blob/main/README.md#contributing`} target="_blank" rel="noopener">
                  Submit a skill on GitHub
                </a>
              </li>
            </ul>
          </div>
          <div className="contact-card">
            <ContactForm />
          </div>
        </div>
      </section>
    </>
  );
}

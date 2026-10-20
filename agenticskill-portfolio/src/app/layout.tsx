import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono, Instrument_Serif } from "next/font/google";
import Link from "next/link";
import { CommandPalette } from "@/components/command-palette";
import { Effects } from "@/components/effects";
import { Header } from "@/components/header";
import { PageFade } from "@/components/page-fade";
import { ArrowRight, ArrowUpRight, Logo } from "@/components/icons";
import { BUILT_BY, CONTACT_EMAIL, REPO_URL, SITE_NAME, buildDate, formatDate, siteUrl, siteVersion } from "@/lib/site";
import { getCategories, searchIndex, stats } from "@/lib/skills";
import "./globals.css";

const sans = Geist({ variable: "--font-geist", subsets: ["latin"], display: "swap" });
const mono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"], display: "swap" });
const serif = Instrument_Serif({
  variable: "--font-instrument",
  subsets: ["latin"],
  weight: "400",
  style: ["normal", "italic"],
  display: "swap",
});

const DESCRIPTION =
  "Production-grade Agent Skills for Claude Code, Codex, Cursor and every agent that reads SKILL.md. Each skill ships instructions, references and tested helper scripts. Search, read and install in one command.";

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl()),
  title: {
    default: `${SITE_NAME} — Agent Skills for Claude Code & AI agents`,
    template: `%s — ${SITE_NAME}`,
  },
  description: DESCRIPTION,
  applicationName: SITE_NAME,
  keywords: ["agent skills", "claude code skills", "SKILL.md", "AI agents", "SQL skills", "Excel skills", "npx skills", "Vector AI Lab"],
  alternates: { canonical: "/" },
  openGraph: {
    type: "website",
    siteName: SITE_NAME,
    url: siteUrl(),
    title: `${SITE_NAME} — Agent Skills for AI agents`,
    description: DESCRIPTION,
  },
  twitter: { card: "summary_large_image", title: SITE_NAME, description: DESCRIPTION },
  robots: { index: true, follow: true },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#ffffff",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  const version = siteVersion();
  const built = buildDate();
  const categories = getCategories();

  return (
    // data-scroll-behavior: keep smooth in-page scrolling, but jump straight to the top on route changes.
    <html
      lang="en"
      data-scroll-behavior="smooth"
      className={`${sans.variable} ${mono.variable} ${serif.variable}`}
    >
      <body>
        <a href="#main" className="sr-only">
          Skip to content
        </a>
        <Header version={version} stats={stats()} />
        <main id="main">
          <PageFade>{children}</PageFade>
        </main>
        <footer className="footer">
          <div className="container">
            <div className="footer-hero">
              <h2>
                Give your agent real expertise.
                <span className="serif">One skill at a time.</span>
              </h2>
              <div className="footer-hero-actions">
                <Link href="/skills/" className="btn footer-btn-primary">
                  Browse skills <ArrowRight />
                </Link>
                <Link href="/contact/" className="btn footer-btn-ghost">
                  Contact us
                </Link>
              </div>
            </div>
            <div className="footer-grid">
              <div className="footer-brand">
                <Link href="/" className="brand">
                  <Logo tone="light" />
                  <span>
                    <b>Vector</b> Agentic Skills
                  </span>
                </Link>
                <p>
                  Open-source Agent Skills for Claude Code and every agent that reads SKILL.md. Each one ships with
                  references and tested scripts.
                </p>
                <a className="built-by" href={BUILT_BY.url} target="_blank" rel="noopener">
                  Built by <b>{BUILT_BY.label}</b> <ArrowUpRight width={14} height={14} />
                </a>
              </div>
              <div>
                <h5>Browse</h5>
                <ul>
                  {categories.flatMap((c) =>
                    c.subcategories.map((sub) => (
                      <li key={`${c.slug}/${sub.slug}`}>
                        <Link href={`/categories/${c.slug}/${sub.slug}/`}>
                          {c.title} / {sub.title}
                        </Link>
                      </li>
                    )),
                  )}
                  <li>
                    <Link href="/skills/">All skills</Link>
                  </li>
                </ul>
              </div>
              <div>
                <h5>Resources</h5>
                <ul>
                  <li>
                    <Link href="/install/">Install guide</Link>
                  </li>
                  <li>
                    <a href="/catalog.json">catalog.json</a>
                  </li>
                  <li>
                    <a href="/dl/all-skills.tar.gz">Download all</a>
                  </li>
                  <li>
                    <a href="/sitemap.xml">Sitemap</a>
                  </li>
                </ul>
              </div>
              <div>
                <h5>Contact</h5>
                <ul>
                  <li>
                    <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>
                  </li>
                  <li>
                    <Link href="/contact/">Contact form</Link>
                  </li>
                  <li>
                    <a href={`${REPO_URL}/issues`} target="_blank" rel="noopener">
                      Request a skill
                    </a>
                  </li>
                </ul>
              </div>
              <div>
                <h5>Contribute</h5>
                <ul>
                  <li>
                    <a href={REPO_URL} target="_blank" rel="noopener">
                      GitHub
                    </a>
                  </li>
                  <li>
                    <a href={`${REPO_URL}/blob/main/README.md#contributing`} target="_blank" rel="noopener">
                      Submit a skill
                    </a>
                  </li>
                  <li>
                    <a href={`${REPO_URL}/blob/main/templates/skill/SKILL.md`} target="_blank" rel="noopener">
                      Skill template
                    </a>
                  </li>
                </ul>
              </div>
            </div>
            <div className="footer-bottom">
              <span>
                © {built.getUTCFullYear()} Vector Agentic Skills
              </span>
              <span className="mono">
                {version} · {formatDate(built)}
              </span>
            </div>
          </div>
        </footer>
        <CommandPalette index={searchIndex()} />
        <Effects />
      </body>
    </html>
  );
}

// Plain constants, safe to import from client components.
export const SITE_URL = "https://agenticskills.vector-ai-lab.com";
export const SITE_NAME = "Vector Agentic Skills";
export const REPO = "MuhammadHusnainAli/vector-agentic-skills";
export const REPO_URL = `https://github.com/${REPO}`;
export const MARKETPLACE = "vector-agentic-skills";
export const AGENTS = ["Claude Code", "Codex", "Cursor", "Gemini CLI", "OpenCode", "GitHub Copilot"];

export const BUILT_BY = { label: "vector-ai-lab.com", url: "https://vector-ai-lab.com" };

export function installCommands(skill: string, subcategory: string) {
  return {
    // Installs from this website via /.well-known/agent-skills (no GitHub round trip).
    npx: `npx skills add ${SITE_URL} --skill ${skill}`,
    claude: `/plugin marketplace add ${REPO}\n/plugin install ${subcategory}-skills@${MARKETPLACE}`,
    curl: `mkdir -p ~/.claude/skills && curl -fsSL ${SITE_URL}/dl/${skill}.tar.gz | tar -xz -C ~/.claude/skills`,
  };
}

export const CONTACT_EMAIL = "agenticskills@vector-ai-lab.com";
/**
 * Web3Forms access key (public by design; it only lets the form send to CONTACT_EMAIL).
 * Set NEXT_PUBLIC_WEB3FORMS_KEY at build time. Without it the form falls back to the visitor's mail app.
 */
export const CONTACT_FORM_KEY = process.env.NEXT_PUBLIC_WEB3FORMS_KEY ?? "";

/** Google AdSense publisher id (public by design: it appears in every page and in /ads.txt). */
export const ADSENSE_CLIENT = "ca-pub-7097433207257153";
/**
 * Ad unit id for the in-page display slot (AdSense > Ads > By ad unit). Set NEXT_PUBLIC_ADSENSE_SLOT at
 * build time; without it the slot renders nothing and only Auto ads (if enabled in AdSense) appear.
 */
export const ADSENSE_SLOT = process.env.NEXT_PUBLIC_ADSENSE_SLOT ?? "";

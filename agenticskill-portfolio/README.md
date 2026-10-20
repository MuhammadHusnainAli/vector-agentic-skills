# Vector Agentic Skills website

The site at [agenticskills.vector-ai-lab.com](https://agenticskills.vector-ai-lab.com). It's a Next.js static export, built from the repository's `../skills` folder and deployed to Cloudflare Pages by [`.github/workflows/deploy.yml`](../.github/workflows/deploy.yml) on every push to `main`.

## Develop

```bash
npm install
npm run dev        # http://localhost:3000
npm run build      # static site in out/
npm run lint
npm run build:local  # static build whose sitemap.xml / robots.txt use http://localhost:4321
npm start            # serve out/ on http://localhost:4321
```

`sitemap.xml`, `robots.txt` and canonical links use `http://localhost:<PORT>` under `npm run dev`, the `SITE_URL` env var when set, and https://agenticskills.vector-ai-lab.com otherwise (CI). Install commands always use the live domain.

`npm run dev` and `npm run build` first run `scripts/sync-skills.mjs`. It copies `../skills` to `public/raw/`, builds tarballs in `public/dl/` (per skill, per sub-category, and all), and copies `../catalog.json`. Those files are generated, so they're gitignored. `public/_headers` sets Cloudflare caching and security headers.

If a local build shows old styles after a CSS change, delete `.next/` and rebuild.

## How it works

| Piece | Where |
|-------|-------|
| Skill loader: category -> sub-category -> skill, frontmatter, references, scripts, git dates | `src/lib/skills.ts` |
| Markdown + Shiki highlighting, link rewriting | `src/lib/markdown.ts` |
| Site URL, repo, install commands | `src/lib/constants.ts` |
| Version shown in the top bar | `src/lib/site.ts` (`SITE_VERSION` env from CI, else `../VERSION` + `-dev`) |
| Sitemap / robots, regenerated every build | `src/app/sitemap.ts`, `src/app/robots.ts` |
| Pages | `/`, `/skills/`, `/skills/[name]/`, `/skills/[name]/[file]/`, `/categories/`, `/categories/[slug]/`, `/categories/[slug]/[sub]/`, `/install/` |
| ⌘K search, hero search, sub-category cards, reference-file popup, terminal demo | `src/components/` |

Adding a skill, sub-category or category under `../skills` needs no code changes. The next deploy adds its pages, search entries, sitemap URLs and downloads. Page navigations use React View Transitions (crossfade, and the skill name morphs from card to page).

## Design

One light theme: white pages with premium green cards and panels, Geist + Instrument Serif, no hover motion. Reference and script files open in a popup (`src/components/file-modal.tsx`) that reuses the prebuilt file pages, so direct links still work. Tokens are at the top of `src/app/globals.css`.

## One-time Cloudflare setup

1. **API token:** Cloudflare dashboard → My Profile → API Tokens → Create Token → "Edit Cloudflare Workers" template, or a custom token with **Account → Cloudflare Pages → Edit**.
2. **GitHub secrets:** repo → Settings → Secrets and variables → Actions → add `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID` (shown on the Cloudflare dashboard sidebar).
3. **First deploy:** push to `main` (or run the workflow manually). The workflow creates the `agenticskills` Pages project if it doesn't exist.
4. **Custom domain:** Cloudflare → Workers & Pages → agenticskills → Custom domains → add `agenticskills.vector-ai-lab.com`. vector-ai-lab.com's DNS is not on Cloudflare, so add the record Cloudflare shows at your DNS provider: a `CNAME` from `agenticskills` to `agenticskills.pages.dev`.

## Contact form

The form on `/contact/` and the home page sends to agenticskills@vector-ai-lab.com through [Web3Forms](https://web3forms.com), which works on static hosting:

1. Go to web3forms.com, enter `agenticskills@vector-ai-lab.com`, and copy the access key it emails you.
2. GitHub repo → Settings → Secrets and variables → Actions → **Variables** → add `WEB3FORMS_ACCESS_KEY` with that key. The key is safe to be public; it can only send to that address.
3. Push to `main`. Until the key is set, the form opens the visitor's email app with the message pre-filled.

For local testing: `NEXT_PUBLIC_WEB3FORMS_KEY=<key> npm run build`.

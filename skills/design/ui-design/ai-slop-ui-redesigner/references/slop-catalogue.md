# Slop Catalogue

Each pattern is fine in isolation and in the right context. It becomes "slop" when it's a default rather than a decision,
and especially when several appear together.

## Visual patterns

| Code | Pattern | How to spot it | Why it reads as AI | Instead |
|------|---------|----------------|--------------------|---------|
| AS001 | Gradient headline text | `bg-clip-text text-transparent`, `background-clip: text` | Default "make it pop" move; weakens legibility | Display typeface, size, weight, or one accent word in the accent colour |
| AS002 | Purple/indigo gradients | `from-purple-600 to-blue-500`, gradients with hue 255-320 | The most common generated palette; says nothing about the brand | Neutral base with a slight tint; one brand accent; gradients only if the brand owns them |
| AS003 | Emoji as icons | 🚀 ✨ ⚡ 🔒 in headings, buttons, cards | Fills the icon slot without a decision; inconsistent rendering per OS | A real icon set at one weight, or no icons |
| AS004 | Glassmorphism cards | `backdrop-blur` + `bg-white/10` | Decoration that lowers contrast | Solid surfaces; elevation from tone or a border |
| AS006 | Glow blobs and orbs | Absolute `blur-3xl` circles, glowing keyframes | Fills empty space with mood instead of content | Product imagery, a real illustration, or deliberate empty space |
| AS007 | Decorative motion | `animate-pulse/bounce/ping` on non-loading UI, float keyframes | Motion without meaning; distracts | Motion only for feedback and transitions; reduced-motion support |
| AS008 | Hover lift everywhere | `hover:scale-105`, `hover:-translate-y-2` on cards and buttons | Everything wiggles, so nothing signals clickability | Clear affordances; hover changes colour/underline; lift only for draggable or truly floating items |
| AS009 | Oversized radius everywhere | `rounded-2xl/3xl` as the default | Soft blobs with no hierarchy | Radius scale: small for controls, medium for containers, full only for pills/avatars |
| AS010 | Heavy shadows everywhere | `shadow-xl/2xl` on every card | Fake depth; muddy | Elevation scale; most surfaces flat; shadows for overlays |
| AS012 | Default Tailwind accent as brand | `bg-indigo-600`, `text-violet-600` as primary | Untouched framework defaults | Brand-derived accent tokens |
| AS013 | Icon in tinted square, three cards | `bg-indigo-100 rounded-xl` icon box in `grid-cols-3` | The single most recognisable template section | Lead with the most important point; use product screenshots; vary the layout |
| AS014 | Inter/system only | No typeface decision | Neutral to the point of anonymous | A pairing chosen for the brand (display + text), tuned scale |

## Content patterns

| Code | Pattern | Examples | Instead |
|------|---------|----------|---------|
| AS005 | Hype copy | Unlock, unleash, seamless, revolutionize, supercharge, elevate, empower, cutting-edge, game-changer, next-level, effortless, all-in-one, "in today's fast-paced world" | Who it's for, what it does, the measurable outcome, how |
| AS011 | Template social proof | "Trusted by 10,000+ teams", "99.9% uptime", "John Doe, CEO at Acme", ★★★★★ | Real named customers with specific results, real logos with permission, or leave it out |
| AS015 | Placeholder content | Lorem ipsum, "Feature 1", example@email.com | Real content; if unavailable, realistic drafts marked for review |

## Copy rewrites

| Slop | Specific |
|------|----------|
| Unlock the power of AI for your business | Draft first replies to support tickets in your help centre's voice, reviewed before sending |
| Seamlessly integrate with your favourite tools | Syncs with Salesforce, HubSpot and Pipedrive every 5 minutes |
| Supercharge your productivity | Cut weekly reporting from 4 hours to 20 minutes |
| Built for the future | Runs in your AWS account; your data never leaves your region |
| Get Started 🚀 | Start a 14-day trial (no card) / Book a 20-minute demo |
| Lightning Fast ⚡ | Pages load in under 1 second on 4G (median, last 30 days) |

Formula: **[Who] [does what] [with what result]**, plus a proof point. Verbs from the user's job, numbers you can stand
behind, nouns from their vocabulary.

## Structural tells

- Hero -> three feature cards -> testimonial -> pricing -> CTA, every section centred and the same height.
- Every section has a badge pill above the heading ("✨ New").
- Stats row of round numbers (10K+, 99.9%, 24/7, 5x).
- Dark mode by default with neon accents, regardless of audience.
- Identical spacing between everything (no grouping).

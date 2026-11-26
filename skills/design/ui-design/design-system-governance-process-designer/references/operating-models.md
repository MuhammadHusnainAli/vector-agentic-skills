# Operating Models

Nathan Curtis's three team models, plus the hybrid most mature systems end up with.

| Model | How it works | Fits | Fails when |
|-------|--------------|------|------------|
| Solitary | One product team's library becomes "the system" for others | Early stage, one dominant product | Other products' needs are ignored; it's that team's library |
| Centralized | A dedicated team builds and maintains the system for everyone | 3+ products, enough funding, need for consistency | Team becomes a bottleneck; disconnected from product reality |
| Federated | Designers/engineers from product teams contribute part-time; no dedicated team | Strong cross-team culture, few products | Nobody has time; quality and consistency drift; no owner for hard decisions |
| Hybrid (centralized core + federated contribution) | Core team owns foundations, quality bar, tooling, releases; product teams contribute components and patterns with support | Most organisations past 3-5 product teams | The core team doesn't invest in supporting contributors |

## Staffing the core team (hybrid)

| Role | Owns |
|------|------|
| Design system lead / product manager | Roadmap, priorities, stakeholder management, metrics |
| Product designers (systems) | Foundations, component design, Figma libraries, design critique |
| Design engineers / front-end engineers | Component code, tokens pipeline, tests, tooling, releases |
| Accessibility specialist (shared or dedicated) | Standards, reviews, testing |
| Content designer (shared) | Content guidelines, component copy |
| Developer relations / advocate (larger orgs) | Docs, onboarding, office hours, champions |

Rough sizing used by practitioners: start with 2-4 people (design + engineering) for a few product teams; grow with the
number of supported platforms and teams. Each extra platform (iOS, Android, web) needs its own engineering capacity.

## Funding

| Model | Pros | Cons |
|-------|------|------|
| Central budget (platform team) | Stable; long-term work possible | Must keep proving value |
| Product teams fund via headcount loans | Close to product needs | Unstable; people get pulled back |
| Chargeback per product | Clear accountability | Bureaucracy; discourages adoption |

Make the business case with: time saved per feature (fewer custom components), defect and accessibility issue reduction,
faster rebrands/theming, design-to-build speed.

## Champions network

One designer and one engineer per product team who:
- attend a monthly systems sync,
- bring their team's needs and contributions,
- spread releases and migrations back to their team.
Recognise their work (performance reviews, credits in release notes).

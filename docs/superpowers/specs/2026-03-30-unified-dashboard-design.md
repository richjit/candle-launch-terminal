# Unified Dashboard — Design Spec

## Purpose

Consolidate Sol Outlook, Launch Monitor, and Narrative Tracker into a single page. Two questions answered on one screen:
1. **Is it a good time to launch?** — health score, SOL chart, launch performance, launchpad activity
2. **What should I launch?** — trending narratives, top runners

## Layout

Three-tier vertical hierarchy (DefiLlama/Nansen pattern):

### Tier 1: Hero Strip

Full-width bar at the top. Answers "should I launch now?" in one glance.

- **Health score** — big number (0-100) with color (green/amber/red)
- **Condensed SOL chart** — ~200px tall candlestick strip with score overlay, interactive
- **Headline stats** inline: launches (24h), graduation rate, survival rate

No scored factors list — health score already incorporates them. Available on click/expand if needed later.

### Tier 2: Launch Conditions

Section header: subtle divider or label.

Two cards side by side (on desktop, stack on mobile):

- **Launch Performance** — existing card with tiers (Best 24h, Top 10%, Bonded), time to peak, all launches median, best performer CA + DexScreener link
- **Launchpad Activity** — existing card with total launches, graduated count, graduation rate, per-platform bar chart

### Tier 3: What to Launch

Section header: "Trending Narratives" or similar.

- **Narrative cards** — grid of narrative cards ranked by momentum (lifecycle badge, token count, volume, avg gain). Click to expand to detail view.
- **Top Runners** — sidebar or below narratives. Top 10 tokens by % gain with narrative tag, age, mcap, DexScreener link.
- **Disclaimer** — red banner about unverified tokens (already exists).

## Pages

- **`/`** — the unified dashboard (replaces current `/pulse`, `/launch`, `/narrative`)
- **`/launch/:metric`** — detail views for launch metrics (keep existing)
- **`/narrative/:name`** — detail view for a specific narrative (keep existing)

Old routes (`/pulse`, `/launch`, `/narrative`) redirect to `/`.

## Sidebar

Remove the 3-page navigation. Either:
- Remove sidebar entirely (single page app, no need)
- Keep sidebar with just the logo/branding

## Data

No backend changes. The unified dashboard fetches from existing endpoints:
- `GET /api/launch/overview` — health score, launch metrics, performance tiers
- `GET /api/narrative/overview` — narratives + top runners
- `GET /api/pulse/chart` — SOL candlestick data
- `GET /api/pulse/correlations` — for health score computation

All on the same polling intervals as before.

## Components

Reuse existing components:
- `LaunchPerformanceCard` — as-is
- `LaunchMigrationCard` — as-is (renamed to Launchpad Activity)
- `LaunchMetricCard` — for survival rate, buy/sell ratio, volume
- `CandlestickChart` — condensed version (reduced height)
- `NarrativeCard` / `RunnerRow` — extract from NarrativeDashboard

New component:
- `UnifiedDashboard.tsx` — the single page that composes everything

## Mobile

- Hero strip stacks: score on top, chart below, stats below that
- Launch cards stack vertically
- Narrative cards go single column
- Top runners below narratives

## Out of Scope

- Scored factors toggle (dropped from main view per design decision)
- Historical chart range selector (the condensed chart shows recent data)
- Any backend changes

# Tests

Two config-driven Playwright/HTTP suites that run against either the TanStack
Start app or a separate Next.js harness. All app-specific values (base URL,
route path, selectors, viewports, tolerances) live in `hero.config.json` and
`head-metadata.expected.json` — the scripts themselves never change per harness.

| File | What it checks |
| --- | --- |
| `hero-headline.py` | Hero H1 wraps into exactly 3 lines, label/headline/CTA left edges align, and each hero screenshot matches its baseline pixel-for-pixel |
| `head-metadata.py` | Rendered `<head>`: title, description, `og:*`, `twitter:*`, canonical |
| `hero.config.json` | Profiles, selectors, viewports, diff tolerances |
| `head-metadata.expected.json` | Expected metadata per route (shared by both harnesses) |

## Requirements

```bash
pip install playwright pillow
python -m playwright install --with-deps chromium
```

No secrets or API keys are required. Optional environment variables:

| Variable | Purpose | Default |
| --- | --- | --- |
| `HERO_BASE_URL` | Convenience for CI; pass it as the positional `base_url` arg | profile's `baseUrl` |
| `PLAYWRIGHT_BROWSERS_PATH` | Where Chromium is installed | Playwright default |

## Running against Next.js (default)

```bash
npm run dev                       # serves http://localhost:3000
python3 tests/hero-headline.py
python3 tests/head-metadata.py
```

## Running against the Next.js harness

The `nextjs` profile in `hero.config.json` points at `http://localhost:3000`
and reuses the same selectors, so the harness only needs to render the hero
markup (`section#top`, `h1 > span` lines, the CTA `a[href="#contact"]`) and
emit the same head tags.

```bash
# in the harness repo
npm run dev                       # serves http://localhost:3000

# back here
python3 tests/hero-headline.py --profile nextjs
python3 tests/head-metadata.py --profile nextjs

# or point at any URL explicitly
python3 tests/hero-headline.py --profile nextjs http://localhost:3001
```

Baselines are stored per profile, so the two harnesses never compare against
each other's renders:

```
tests/baselines/tanstack/hero-<viewport>.png
tests/baselines/nextjs/hero-<viewport>.png
```

## Updating baselines

Do this only after an intentional design change, and commit the new PNGs.

```bash
python3 tests/hero-headline.py --update-baseline                  # tanstack
python3 tests/hero-headline.py --profile nextjs --update-baseline # nextjs
```

Missing baselines are recorded automatically on first run, so a brand-new
profile bootstraps itself.

## Useful flags

```bash
--viewports mobile-375,desktop-1280   # run a subset
--baseline-dir path/to/dir            # compare against a different baseline set
--report out.json                     # machine-readable results (used by CI)
```

## Reading a failure

On a pixel mismatch the script writes
`tests/diffs/<profile>/hero-<viewport>-diff.png` — a three-panel image:
**baseline | current | changed pixels highlighted in magenta**. CI uploads
both `tests/screenshots` and `tests/diffs` as artifacts and posts a summary
comment on the pull request naming the failing viewports.

## Faster local debugging, retries and the HTML gallery

- `--only <names|widths>` runs a subset: `--only desktop-1280`, `--only 375,1280`,
  or a name fragment like `--only mobile`. `--viewports` remains as an alias.
- `--retries N` (default `retries` in `hero.config.json`, currently 2) re-runs a
  viewport that fails so transient font/image settling doesn't fail a PR. A
  viewport that only passes after a retry is reported as `flaky` in the JSON
  report and flagged in the PR comment; diff images are only written on the
  final attempt. `retryDelayMs` controls the pause between attempts.
- Every run writes an HTML gallery to `tests/report/hero-gallery-<profile>.html`
  (override with `--gallery <path>`, skip with `--no-gallery`). It lists failed
  viewports first with inline baseline|current|diff triptychs, and is uploaded
  with the CI artifacts for review.

## Quarantine, targeted baseline updates and stabilization

- `--update-only-failures` reads the last JSON report (`tests/report-hero.json`
  by default, or `--last-report <path>`) and re-records baselines **only** for
  the viewports that failed there. Every passing baseline is left byte-identical.
  Exits 0 with a note when the last run was clean.
- `--quarantine mobile-320,tablet-768` (or a `"quarantine": [...]` array in
  `hero.config.json`, or the `HERO_QUARANTINE` env var in the CI workflow) marks
  viewports as known-flaky: they still run, still screenshot, still appear in the
  report and gallery as `QUARANTINED`, but their failures don't set a non-zero
  exit code, so PRs aren't blocked by known transient issues. Names, widths or
  name fragments all match.
- Before every capture the page is stabilized: CSS animations/transitions are
  zeroed and running animations finished, `prefers-reduced-motion: reduce` is
  set, videos paused, the caret hidden, `document.fonts.ready` awaited, pending
  images decoded, scroll reset to top, `networkidle` awaited and two animation
  frames flushed. This removes the usual sources of one-off pixel drift.

## FeaturedWork carousel padding (`tests/featured-work-padding.py`)

Asserts the first work card's left edge matches the section heading/label left
edge (and that the snap container isn't self-scrolled) at every viewport in
`hero.config.json`, within `paddingTolerance`.

```bash
python3 tests/featured-work-padding.py --help                   # full flag reference + examples
python3 tests/featured-work-padding.py                          # tanstack (default), all viewports
python3 tests/featured-work-padding.py --profile nextjs
python3 tests/featured-work-padding.py --viewports mobile,tablet  # group aliases
python3 tests/featured-work-padding.py --viewports desktop-1440,375  # exact names or widths
python3 tests/featured-work-padding.py --padding-tolerance 1.5  # allow sub-pixel drift only
python3 tests/featured-work-padding.py --update-baseline        # re-record per-viewport offsets
python3 tests/hero-headline.py --only-featured-work             # skip the hero suite entirely
python3 tests/hero-headline.py --only-featured-work --tolerance 1.5  # forwarded through
```

`--viewports` (alias `--only`) accepts the group aliases `mobile`, `tablet`,
`laptop`, `desktop`, `all`, plus exact viewport names and widths.

`--padding-tolerance` (alias `--tolerance`) overrides `paddingTolerance` from
`hero.config.json` — use a small value like `1` or `1.5` to allow only sub-pixel
drift, a larger one to loosen the assertion.

Baseline offsets live in `tests/baselines/featured-work-offsets-<profile>.json`.
Each run also compares the current delta against that baseline and fails if the
drift exceeds the tolerance.

Every run captures an annotated screenshot of the `#work` section
(`tests/screenshots/featured-work/<profile>-<viewport>.png`) with a red guide
line on the heading's left edge, a blue line on the first card, and a badge
showing `delta · baseline · tolerance`, plus a per-viewport diff image
(`tests/diffs/featured-work/<profile>-<viewport>-diff.png`) that draws the
recorded baseline card edge as a dashed amber line, hatches the gap against the
current edge, and badges `delta · baseline · drift · tolerance`. Pass
`--no-diff-images` to skip them. Both are shown side by side in
`tests/report/featured-work-gallery-<profile>.html` (failures first), uploaded
as a CI artifact and linked from the PR comment.

Outputs per run:

| File | Purpose |
| --- | --- |
| `tests/report-featured-work.json` | full run report |
| `tests/report/featured-work-summary-<profile>.json` | machine-readable summary: per-viewport left edge, baseline, delta, drift, tolerance, pass/fail, artifact paths (override with `--summary`) |
| `tests/report/featured-work-gallery-<profile>.html` | HTML gallery |
| `tests/screenshots/featured-work/` , `tests/diffs/featured-work/` | annotated + diff images |

All of these are uploaded together in the `hero-visual-regression` CI artifact;
the suite runs on every PR in the hero workflow.


## FeaturedWork lightbox end-to-end (`tests/featured-work-lightbox.py`)

```bash
python3 tests/featured-work-lightbox.py                       # all checks
python3 tests/featured-work-lightbox.py --base-url http://localhost:3000
python3 tests/featured-work-lightbox.py --report none         # skip the JSON report
```

Verifies that:

- `/?work=<slug>` opens the matching item on a hard refresh, with cumulative
  layout shift under 0.02 (the lightbox reserves the image ratio) and the body
  scroll lock applied while open and released on close;
- prev/next and the arrow keys keep the `work` search param in sync, and the
  neighbouring images are already decoded before navigation;
- the lightbox reports `data-reduced-motion="true"` and runs with no animation
  or transition duration under `prefers-reduced-motion: reduce`;
- clicking a card deep-links its slug, and closing (Escape) returns focus to
  that exact card and clears the param.

Writes `tests/report-lightbox.json`; runs on every PR in the hero workflow.

## Header word mark (`tests/header-logo.py`)

Covers the "Brand Ledger" logo in the header:

- **a11y** — accessible name is exactly `Brand Ledger`, it's a real link, first
  Tab stop, has a visible focus indicator, and the whole `<header>` passes an
  axe-core WCAG 2.1 AA scan (colour-contrast included).
- **layout** — sweeps 11 viewport resizes (320 → 1920 and back down) asserting
  the word mark never overlaps the desktop nav or hamburger toggle, stays on a
  single line, honours the header container padding and stays inside the bar.
- **snapshot** — pixel diffs the word mark at mobile (375) and desktop (1280),
  each at 1x **and retina `deviceScaleFactor: 2`**, against
  `tests/baselines/header-logo-<browser>-<viewport>[@2x].png` (max 1% changed
  pixels; diffs go to `tests/diffs/`).
- **zoom** — re-renders the header at 125% and 150% browser zoom (CSS viewport
  divided by the zoom factor, rastered at that device scale factor) and asserts
  the word mark stays on one line, keeps container alignment, never overlaps
  the nav/toggle, plus a pixel snapshot per zoom level.
- **tap** — the word mark's hit box is at least 44x44 px on mobile and 24 px
  tall on desktop, and pointer hits across the box land on the link itself.

Layout, zoom, snapshot and tap cases run per engine — Chromium, Firefox and
WebKit (Safari's engine) — so the larger word mark is proven not to overlap the
nav after resizes on any of them. Baselines are per engine.

```bash
python3 tests/header-logo.py                                   # chromium, all cases
python3 tests/header-logo.py --browsers chromium,firefox,webkit
python3 tests/header-logo.py --only a11y,layout,tap            # skip pixel work
python3 tests/header-logo.py --only zoom                       # zoom checks only
python3 tests/header-logo.py --update-baseline                 # re-record snapshots
python3 tests/header-logo.py --report tests/report-header-logo.json
```

Runs on every PR in `.github/workflows/hero-visual-regression.yml`; results are
summarised in the PR comment and screenshots/diffs ship in the artifact.


## Section semantics, contrast and transition suites

```bash
python3 tests/section-semantics.py        # one h1/main, heading order, axe (all breakpoints + short viewports)
python3 tests/section-contrast.py         # AA contrast measured from rendered pixels, per section
python3 tests/section-transitions.py      # boundary-band snapshots + luminance/divider checks
python3 tests/section-transitions.py --update-baseline
python3 tests/section-transitions.py --update-only-failures
python3 tests/section-transitions.py --only desktop-1440 --boundaries work-capabilities
python3 tests/section-transitions.py --quarantine short-812 --retries 3
```

All three accept `--profile nextjs`, `--browsers`, `--only` and `--orientation`, and write
`tests/report-section-*.json`. Transition bands additionally render
`tests/report/section-transitions-<profile>.html` for artifact review.


## Footer contact (`tests/footer-contact.py`)

Verifies the SiteFooter Contact column stays correct:

- email text is exactly `hello@thebrandledger.com`;
- email is a clickable `mailto:hello@thebrandledger.com` link;
- location reads `Omaha, NE`;
- no phone number text, separators, or placeholders appear in the contact column;
- pixel snapshots of the full footer at mobile (375) and desktop (1280).

```bash
python3 tests/footer-contact.py
python3 tests/footer-contact.py --update-baseline
python3 tests/footer-contact.py --report tests/report-footer-contact.json
```

Baselines live in `tests/baselines/footer-contact/`. Diffs go to
`tests/diffs/footer-contact/`. Runs on every PR in the hero workflow and is
summarised in the PR comment.


## Footer layout (`tests/footer-layout.py`)

Pixel-perfect check of the SiteFooter at 8 breakpoints (320, 375, 414, 768,
1024, 1280, 1440, 1920). The footer is split into three **independent
sections** so a failure names the exact block that regressed:

| Section | Captured | Structural assertions |
| --- | --- | --- |
| `links` | the link-column grid | 1 / 2 / 4 columns per row, first column on the container padding edge, dynamic copyright year |
| `divider` | the rule above the columns | spans the full container content width |
| `watermark` | `MADE IN OMAHA` | stays on one line, never overflows the content box |

Each section has its own baseline, its own diff image, its own retry budget and
its own entry in the JSON report — one block failing never re-baselines or
masks the others.

```bash
python3 tests/footer-layout.py
python3 tests/footer-layout.py --update-baseline
python3 tests/footer-layout.py --section watermark          # one block
python3 tests/footer-layout.py --section links,divider --only 320,desktop-1440
```

Baselines live in `tests/baselines/footer/<section>/`; failures write a
baseline | current | highlighted triptych to `tests/diffs/footer/<section>/`
and bundle the triplet into `tests/report/footer-failures/<section>/`.
The report carries a `sections` summary listing failed viewports per block.
Flaky frames are retried twice (only still-failing sections re-run) before a
section fails. Runs on every PR.



## Mobile navigation suite and slow dev servers

`tests/mobile-nav.py` waits for the dev server to answer before launching the
browser, retries the initial navigation, and opens the menu by retrying the
toggle click until `aria-expanded="true"` and `#mobile-menu` are both true —
so a still-compiling Vite server no longer produces a spurious timeout.

```bash
python3 tests/mobile-nav.py
python3 tests/mobile-nav.py --only resize,navigation
python3 tests/mobile-nav.py --timeout 90000   # slower/loaded CI machines
```

### Retries, quarantine and flake rate

Each case (`resize`, `navigation`, `aria-current`, `axe`) runs on its own and is
retried before it counts as a failure, so a one-off timeout does not block a PR.
Only the last attempt's checks are reported.

```bash
python3 tests/mobile-nav.py --retries 2              # default
python3 tests/mobile-nav.py --quarantine axe         # reported, never blocking
python3 tests/mobile-nav.py --retries 0              # strict, no retries
```

- `--retries N` — attempts per case beyond the first (default `2`).
- `--quarantine a,b` — known-flaky cases that are reported but never fail the run.
  In CI set the `MOBILE_NAV_QUARANTINE` env var on the mobile-nav workflow step.
- `--flake-history PATH` — rolling history (default
  `tests/report/mobile-nav-flake-history.json`, last 50 runs) used to compute a
  per-case flake rate.

`tests/report-mobile-nav.json` gains `cases`, `retries`, `quarantined`,
`flakeRate`, `totalAttempts` and a `history` block; the PR comment renders a
"Mobile navigation" section with recovered-on-retry cases, quarantined cases and
a per-case flake-rate table. Exit code is non-zero only for non-quarantined
cases that still fail after all retries.


## Shared projects data integrity

```bash
bun test tests/projects-data.test.ts
```

Fails if any entry in `src/lib/projects.ts` is missing a field the footer and carousel
depend on (`slug`, `name` display title, `category`, `image`, `alt`, `note`), if slugs
are duplicated or not URL-safe, or if the derived footer deep link
(`/?work=<slug>#work`) cannot be built.

## Footer accessibility

```bash
python3 tests/footer-a11y.py --report tests/report-footer-a11y.json
```

Checks meaningful accessible names for every footer link, no positive `tabIndex`,
duplicate link text pointing at different destinations, keyboard tab order matching
DOM/visual order per column, a visible focus indicator on each focused link, the
`mailto:` link announcing the address, and an axe-core (WCAG 2 A/AA) scan scoped to
`footer#contact`. It makes no visual changes.

## Footer Work link routing

```bash
python3 tests/footer-work-links.py --report tests/report-footer-work-links.json
```

Reads the shared projects array from `src/lib/projects.ts` (via `bun`) and, for every
project, clicks its footer Work link, asserts the URL becomes `/?work=<slug>#work`,
asserts the lightbox opens with that project's category, title, note and accessible
name, checks the same deep link on a cold page load, and confirms closing the lightbox
clears the `?work` param.

## Unknown work slug fallback

```bash
python3 tests/footer-work-invalid-slug.py --report tests/report-footer-invalid-slug.json
```

Deep links `?work=<bogus>#work` (typos, display titles, path traversal, script
injection, empty value) and asserts the page still renders, no lightbox opens, no
console/page errors fire, the stale `?work` param is stripped while `#work` is kept,
and a real footer project link still opens its lightbox afterwards.

## Deep-link reload restores lightbox and focus

```bash
python3 tests/footer-work-reload.py --report tests/report-footer-work-reload.json
```

For every project, loads `/?work=<slug>#work`, reloads that same URL, and asserts the
lightbox is restored with the right category/title/note and accessible name, that focus
lands inside the dialog and stays trapped while tabbing, that `?work=<slug>` and `#work`
survive the reload, and that Escape closes the dialog and returns focus to that
project's carousel card.


## Sequential footer Work clicks

```bash
python3 tests/footer-work-sequence.py --report tests/report-footer-work-sequence.json
```

On one page load, clicks every footer Work link forward, in reverse and in an
alternating pass (16 steps). After each click it asserts the lightbox shows only that
project's category, title, note, image and alt, that no other project's content lingers,
that the URL is `/?work=<slug>#work`, that focus is inside the dialog, and that Escape
returns focus to that project's carousel card and clears `?work`. Fails on any console
or page error during the sequence.

## Back/forward lightbox state

```bash
python3 tests/footer-work-history.py --report tests/report-footer-work-history.json
```

Builds a real history stack by opening and closing every project from the footer, then
walks the stack all the way back and forward again. At each stop the UI must match the
URL: `?work=<slug>` restores that project's lightbox (title, category, note, alt, focus
inside the dialog) and a URL without `?work` must have no lightbox in the DOM. Also
checks no stale project content survives a history step and that reopening a project
after back/forward still works, with no console or page errors.

# Brand Ledger

The Brand Ledger studio site — a one-page marketing site on Next.js 16 (App
Router, React 19, Tailwind v4), deployed to Vercel at
[thebrandledger.com](https://thebrandledger.com).

It began life in a visual builder on TanStack Start (Vite) and was converted to
Next.js. Nothing of that origin remains in the shipped app; the conversion notes
are kept in [Origins](#origins) at the end because a few decisions only make
sense against it.

## Development

```sh
npm install
npm run dev        # http://localhost:3000
```

| Script | What it does |
| --- | --- |
| `npm run dev` | Dev server on :3000 |
| `npm run build` | Production build |
| `npm run start` | Serve the production build on :3000 |
| `npm run lint` | ESLint (`eslint-config-next` + prettier) |
| `npm run typecheck` | `tsc --noEmit` |
| `npm run test:data` | Projects data-integrity test (`node --test`) |

Nineteen Playwright suites live in `tests/` — see `tests/README.md`. Several
compare against committed pixel baselines and **only pass in CI**; see
[Test baselines](#test-baselines) before running them locally.

`scripts/build-og-image.py` regenerates the social card.
`scripts/build-font-fallbacks.py` regenerates the metric-matched font overrides.

## Configuration

Everything shared lives in `lib/site.ts` — name, description, contact details,
address. The footer and the JSON-LD both read from it, so they cannot drift.

| Variable | Purpose | Default |
| --- | --- | --- |
| `NEXT_PUBLIC_SITE_URL` | Origin for `canonical`, `og:url`, the sitemap and JSON-LD | `https://thebrandledger.com` |
| `NEXT_PUBLIC_FORMSPREE_ENDPOINT` | Where the contact form posts | the studio's form |

Set both on preview and staging deploys: the first stops a preview advertising
the production URL as its canonical, the second keeps test submissions out of
the real inbox.

## Design

Cream, ink and a single red accent, defined once as oklch tokens in
`app/globals.css` and consumed everywhere else through Tailwind. Anton for
display, Barlow for text. Radius is `0` throughout.

**No photography.** The hero and the three service pillars are typographic:
flat ink fields, oversized ghost numerals, hairline rules and a red mark under
each heading. They previously ran on stock imagery in colours the brand does not
use, carrying visible generation artefacts — a fabricated logo, gibberish body
text, illegible handwriting. For a studio selling design and content judgement
that is the wrong first impression, and the hero photograph also contradicted
the positioning by showing a large agency floor for a one-person studio.

The one photograph on the page is the Heartland Plein Air Festival thumbnail,
which is a capture of real work.

If imagery is ever reintroduced it has to be real — the work, the workspace, or
Omaha. The icon set follows the same rule: `app/icon.svg` is built from actual
Anton outlines extracted from `public/fonts/anton-400.woff2`, so the mark is
true vector with no font dependency.

### The headline

Two size ramps, because the two layouts have different limits.

Below `md` the three spans are allowed to wrap, so the binding constraint is the
longest **word**: `EXPERIENCED` measures 4.77 × the font size, which at a 320px
viewport's 280px of measure caps it near 58px. The ramp is `12.2vw` capped at
`3.3rem`, which spends that headroom where it exists — a 320px phone keeps
`2.6rem` exactly, a 393px iPhone gets ~48px, a 430px Pro Max ~52px — without
pushing the CTAs below the fold. A flat floor could not do that: the headline is
four rows tall on a phone, so every extra pixel costs vertical space, and at
320×568 and 360×640 the CTAs already sit under the fold.

From `md` the spans are `nowrap` and the constraint is the longest **line** at
8.83 ×, which is what the `6.6vw` ramp and its `9rem` ceiling are sized for. The
block widens to `82rem` to hold it; at `68rem` the line overflowed and was
silently clipped by the stage's `overflow-hidden` rather than raising a
scrollbar.

Line height is `1.04` below `md` and `0.93` from `md` up. The `.display` utility
sets `0.93` for spans that are always one line, where it controls the gap
between the three lines of the masthead. Once a span wraps, that same `0.93`
applies *inside* it, which left under 3px between one row's cap bottom and the
next row's cap top.

### The scroll cue

A hero that fills the viewport gives no signal that the page continues, so the
base of the stage carries a cue. It is a real link to `#services` rather than
decoration — an affordance that looks clickable but cannot be reached by
keyboard is worse than none.

It appears only above 780px of viewport height. Below that the four-row headline
makes the hero taller than the viewport, and the cue rendered either on top of
the CTA row or below the fold — and a cue marking the edge of the first screen
is useless when it is not on the first screen. On those viewports the CTA row
already sits against the bottom edge and signals the same thing without a label.

## Analytics and consent

GA4 (`G-09TDRM4HQ8`) is installed behind Google Consent Mode rather than firing
on load, because the cookie bar offers a real Decline.

`components/Analytics.tsx` sets every storage type to `denied` before `gtag.js`
loads — consent defaults are only honoured if they reach `dataLayer` first,
which is why that script is inline and `beforeInteractive`. `CookieBar` calls
`setAnalyticsConsent` on a choice, so Decline actually denies rather than just
hiding the bar. A returning visitor's stored Accept is re-granted on load.

Verified against a production build: no `_ga` cookie exists before consent, it
appears after Accept, and Decline leaves the visitor cookieless. Worth checking
against `next start` rather than `next dev` if this is ever touched —
`beforeInteractive` compiles differently in production.

## SEO

- **Canonical and `og:url` are absolute**, derived from `metadataBase`. Relative
  values are dropped or mis-resolved by several social scrapers.
- **`app/sitemap.ts` generates itself.** `lib/routes.ts` walks the app directory
  at build time and derives a path for every `page` file, so a new page is in
  `/sitemap.xml` by existing. Route groups, private folders, parallel slots,
  intercepting routes, dynamic segments and `api/` are each handled explicitly,
  since treating them alike publishes URLs that 404. Dynamic segments are the
  one case discovery cannot resolve — their addresses live in data — so
  `DYNAMIC_ROUTES` is the seam for them.
- **`?work=` deep links stay out of the sitemap.** They render the same document
  with a lightbox over it and canonicalise back to `/`, so listing them would
  offer crawlers near-duplicates to reconcile against a canonical that disagrees
  with all of them. Sitemap URLs carry no trailing slash, matching the canonical
  byte for byte.
- **JSON-LD** in `lib/structured-data.ts`: a `ProfessionalService` with full
  `PostalAddress`, phone, email, founder and an `OfferCatalog` of five services;
  a `WebSite`; and an `ItemList` of the featured work. A one-page site otherwise
  gives crawlers nothing to resolve the entity against.
- **`public/og.jpg`**, a 1200×630 card built by `scripts/build-og-image.py`.
- **Icons**: `favicon.ico` carries three separately rendered entries (16/32/48)
  rather than one master downsampled, because the large mark's proportions land
  on fractional pixels at those sizes. `app/manifest.ts` supplies the 192/512
  PNGs Android reads for its install prompt.

## Accessibility

- A skip link is the first tab stop, so keyboard and switch users do not tab the
  fixed masthead on every visit (WCAG 2.4.1).
- `autocomplete` on the contact fields (WCAG 1.3.5).
- Each "Learn More" pillar link carries its pillar name as an accessible name;
  three identical links are indistinguishable in a screen reader's link list.
- The postal address is an `<address>` element, not a link — an address is a
  fact, not a destination, and as a link it was an unlabelled dead end.
- Footer contact icons are `aria-hidden`; each duplicates a label already there.
- An `aria-live` region announces form confirmation, since the toast alone is
  not reliably announced.
- The back-to-top control unmounts when hidden rather than being visually
  hidden, so there is never an invisible focusable control.

`section-contrast` measures every text role against the pixels actually painted
behind it and asserts WCAG AA. `footer-a11y` and `section-semantics` (axe-core)
cover the rest.

## Contact form

The footer form posts to Formspree. It carries a real `action`/`method`, so with
JavaScript disabled the browser posts natively and lands on Formspree's
thank-you page; with JavaScript, `onSubmit` intercepts and sends the same
`FormData` over `fetch` (with `Accept: application/json`, without which
Formspree answers with a redirect rather than JSON) so the visitor stays put.

Two hidden fields ride along: `_subject` names the notification email, and
`_gotcha` is a honeypot Formspree uses to discard bot submissions.

The three outcomes are handled distinctly, because the failure modes matter more
than the happy path:

| Outcome | Behaviour |
| --- | --- |
| Success | Form clears, button reads "Inquiry Sent", toast + `role="status"` announcement |
| Formspree rejects | Its message shown in a `role="alert"`, **inputs preserved**, button resets to allow a retry |
| Network failure | Same, with a fallback message pointing at the direct email address |

Nothing the visitor typed is discarded on a failure — only a confirmed success
resets the form.

The form sits on its own cream panel rather than transparent on the red footer,
where the fields had almost nothing separating them from the background.

## Fonts

Anton and Barlow are self-hosted Latin subsets, preloaded, at
`font-display: block`.

`swap` was tried and backed out — not because it was measured to break anything,
but for sequencing: `swap` lets text paint in a fallback, which is one more
variable between a capture and the frame it was meant to catch, and introducing
that while the regression suite was still being stabilised is the wrong order.
Worth revisiting as an isolated change now that CI is green; the faces are
preloaded and subsetted, so the window `block` withholds text for is short.

The metric-matched fallbacks in `app/fonts.css` are kept regardless. If the 3s
block period does elapse on a bad connection, the fallback that takes over holds
the same line box and average advance, so the page does not reflow when the real
face lands. Measured with the webfonts stalled three seconds:

| Viewport | With metric matching | Without |
| --- | --- | --- |
| 390px | no text reflow | About paragraph 6 → 5 lines (156 → 130px) |
| 768px | no text reflow | Capabilities paragraph 5 → 4 lines (130 → 104px) |

`scripts/build-font-fallbacks.py` computes the overrides from the font tables —
re-run it if a face is swapped or resubsetted. They are `local()`-only, so they
cost no download and do not apply where those system faces are absent.

## CI

`.github/workflows/hero-visual-regression.yml` runs all nineteen suites against
a production build on `ubuntu-latest`, on pushes to `main`, on pull requests,
and on demand.

**A missing baseline is recorded and the suite passes.** That is what makes a
first run green, and it is also a trap: a suite with no committed baseline
compares nothing. The run uploads a `recorded-baselines` artifact for exactly
this reason — download it, commit the contents, and the next run becomes a real
comparison.

## Test baselines

`tests/baselines/` holds 229 PNGs recorded on `ubuntu-latest` against a
production build.

**Never record baselines on a developer machine.** `scrollbar-gutter: stable`
reserves 15px against a classic scrollbar on Linux and 0px against macOS's
overlay scrollbars, so every local capture is 15px narrower and can never match
CI. This is not a subtle difference: on macOS *every* pixel suite fails at 100%
diff, including ones whose components have not been touched. Run the
baseline-backed suites in CI and the behavioural ones locally.

When a design change legitimately invalidates a baseline:

1. Delete only the baselines that changed and push.
2. CI records fresh ones and goes green.
3. Download the `recorded-baselines` artifact and commit its contents.

**Delete precisely, not by directory.** Retiring a whole folder blesses whatever
else drifted inside it without anyone looking. A worked example: enlarging the
mobile headline moved exactly one of 168 transition bands — a 1px hairline
landing on a different pixel row because the taller hero shifted the boundary's
absolute offset. Retiring that single file and re-recording confirmed the other
167 were byte-identical.

Two checks are worth running on a downloaded artifact before committing it:

- **`header-logo` should come back byte-identical** whenever the masthead has
  not been touched. It is the control that says CI reproduces, which is what
  makes the files that *did* change trustworthy.
- **The changed files should match what the change predicts.** After the
  headline ramp, `hero-mobile-320` was byte-identical (12.2vw of 320px is under
  the floor, so the smallest phone was deliberately left alone) while
  `hero-mobile-375` and `hero-mobile-414` differed, and tablet and desktop were
  identical — confirming the `md` ramp was genuinely untouched rather than
  approximately so.

## Carried-over lint warnings

`npm run lint` reports 0 errors and 12 warnings. They are all pre-existing
patterns — `set-state-in-effect` in the SSR-safe "sync after mount" hooks,
`refs` in FeaturedWork's focus-restore mirror, `purity` in shadcn's untouched
`sidebar.tsx`. `eslint.config.mjs` documents each one. They are worth
revisiting, but the Playwright suite pins the behaviour they produce, so they
are warnings rather than errors.

## Origins

The site was converted from a TanStack Start (Vite) build generated in a visual
builder. The conversion was verified by screenshotting every section at all ten
viewports against both apps side by side: 0.000000 diff ratio across all 60
comparisons. The design has since moved well past that baseline on purpose.

| TanStack Start | Next.js |
| --- | --- |
| `src/routes/__root.tsx` shell + `head()` | `app/layout.tsx` (`metadata`, `viewport`) |
| `src/routes/index.tsx` | `app/page.tsx` |
| `notFoundComponent` / `errorComponent` | `app/not-found.tsx` / `app/error.tsx` |
| `src/router.tsx`, `routeTree.gen.ts` | file-system routing (deleted) |
| `src/server.ts`, `src/start.ts` | handled by Next (deleted) |
| `QueryClientProvider` in the root route | `app/providers.tsx` (client) |
| `useSearch()` / `useNavigate()` | `useSearchParams()` + History API |
| `src/assets/*.jpg` module imports | `public/images/*` string paths |
| `src/styles.css` (`@source "../src"`) | `app/globals.css` (`@source` per top-level dir) |
| Tailwind via `@tailwindcss/vite` | Tailwind via `@tailwindcss/postcss` |

Three decisions from that period still hold:

**Images stay plain `<img>`.** Nothing goes through `next/image`. The layout
depends on `object-cover` crops and a fixed aspect ratio, and the optimizer's
`srcset`/`sizes` rewriting would only risk moving pixels. `WorkImage`'s
skeleton, decode timing and retry fallback already cover what it would provide.

**`?work=` is read with `useSearchParams()` and written with the History API.**
Next patches `pushState`/`replaceState` and feeds them back into the hook, so the
lightbox opens with no RSC round trip while back/forward keep working.
`app/page.tsx` sets `dynamic = "force-dynamic"` so a deep-linked `?work=<slug>`
resolves on the server and the hook needs no Suspense boundary, which would
otherwise keep Featured Work out of the SSR payload.

**`FeaturedWork` re-asserts focus into the lightbox on a closed → open edge.**
Radix keeps the dialog mounted for the length of its exit animation, so a history
step that closes and immediately reopens it reuses the same node — the focus
scope never remounts, Radix's open-autofocus never fires again, and focus is
stranded on `<body>`. `footer-work-history.py` covers all 28 history stops.

Assets and copy inherited from the builder have been removed as they surfaced:
its logo was still serving as the favicon, an error-reporting module forwarded to
globals that only existed inside its editor preview, and the Heartland thumbnail
was hotlinked from its asset CDN and 404'd after the migration.

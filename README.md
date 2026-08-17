# Brand Ledger — Next.js

The Brand Ledger one-page site, converted from the Lovable/TanStack Start (Vite)
build to Next.js 16 (App Router, React 19, Tailwind v4).

The conversion was verified by screenshotting every section at all ten viewports
in `tests/hero.config.json` against both apps running side by side: **0.000000
diff ratio, no size mismatches**, across all 60 comparisons.

Two sections have since moved on from that baseline on purpose — Featured Work,
whose Heartland thumbnail was restored, and the hero, which was rebuilt (see
below). Everything else still matches the original byte for byte.

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

Playwright suites live in `tests/` — see `tests/README.md`.
`scripts/build-og-image.py` regenerates the social card.

## Configuration

`NEXT_PUBLIC_SITE_URL` sets the origin used for `canonical`, `og:url`, the
sitemap and JSON-LD. It defaults to `https://thebrandledger.com` (inferred from
the studio's contact address in the footer) — **confirm that is the production
domain**, and set the variable on preview/staging deploys so they do not
advertise the production URL.

`NEXT_PUBLIC_FORMSPREE_ENDPOINT` sets where the contact form posts. It defaults
to the studio's Formspree form. Point preview deploys at a throwaway form so
test traffic stays out of the real inbox. Everything else lives in `lib/site.ts`.

## Contact form

The footer form posts to Formspree. It carries a real `action`/`method`, so
with JavaScript disabled the browser posts natively and lands on Formspree's
thank-you page; with JavaScript, `onSubmit` intercepts and sends the same
`FormData` over `fetch` (with `Accept: application/json`, without which
Formspree answers with a redirect rather than JSON) so the visitor stays put.

Two hidden fields ride along: `_subject` names the notification email, and
`_gotcha` is a honeypot Formspree uses to discard bot submissions.

The three outcomes are handled distinctly, because the failure modes matter
more than the happy path:

| Outcome | Behaviour |
| --- | --- |
| Success | Form clears, button reads "Inquiry Sent", toast + `role="status"` announcement |
| Formspree rejects | Its message is shown in a `role="alert"`, **inputs are preserved**, button resets so the visitor can retry |
| Network failure | Same, with a fallback message pointing at the direct email address |

Nothing the visitor typed is ever discarded on a failure — only a confirmed
success resets the form.

## How the conversion maps

| TanStack Start | Next.js |
| --- | --- |
| `src/routes/__root.tsx` shell + `head()` | `app/layout.tsx` (`metadata`, `viewport`) |
| `src/routes/index.tsx` | `app/page.tsx` |
| `notFoundComponent` / `errorComponent` | `app/not-found.tsx` / `app/error.tsx` |
| `src/router.tsx`, `routeTree.gen.ts` | file-system routing (deleted) |
| `src/server.ts`, `src/start.ts` (SSR error wrapper, CSRF) | handled by Next (deleted) |
| `QueryClientProvider` in the root route | `app/providers.tsx` (client) |
| `useSearch()` / `useNavigate()` | `useSearchParams()` + History API |
| `src/assets/*.jpg` module imports | `public/images/*.jpg` string paths |
| `src/styles.css` (`@source "../src"`) | `app/globals.css` (`@source` per top-level dir) |
| Tailwind via `@tailwindcss/vite` | Tailwind via `@tailwindcss/postcss` |

Everything under `components/`, `hooks/` and `lib/` is otherwise carried over
verbatim, with `"use client"` added where the App Router needs it.

### Notes on three decisions

**Images stay plain `<img>`.** Nothing goes through `next/image`. The layout
depends on `object-cover` crops and a fixed aspect ratio, and the optimizer's
`srcset`/`sizes` rewriting would only risk moving pixels. `WorkImage`'s skeleton,
decode timing and retry fallback already cover what `next/image` would provide.

**`?work=` is read with `useSearchParams()` and written with the History API.**
Next patches `pushState`/`replaceState` and feeds them back into the hook, so the
lightbox opens with no RSC round trip — matching the instant feel of the
TanStack `navigate({ search: { work } })` calls — while back/forward keep working.
`app/page.tsx` sets `dynamic = "force-dynamic"` so a deep-linked `?work=<slug>`
is resolved on the server and the hook needs no Suspense boundary that would
otherwise keep Featured Work out of the SSR payload.

**SEO output is built from `metadataBase`.** The conversion initially
hand-rendered `og:url` and `canonical` to reproduce the original's literal `"/"`.
The audit reversed that: relative values are dropped or mis-resolved by several
social scrapers, so both are now absolute and `tests/head-metadata.expected.json`
was updated to match. `head-metadata.py` passes all 16 assertions.

### One behavioural fix

`FeaturedWork` re-asserts focus into the lightbox on a closed → open edge. Radix
keeps the dialog mounted for the length of its exit animation, so a history step
that closes and immediately reopens it reuses the same node — the focus scope
never remounts and Radix's own open-autofocus never fires again, stranding focus
on `<body>`. The original had the same latent race; the History API updates fast
enough to expose it. `footer-work-history.py` covers all 28 history stops.

## Audit fixes

A full SEO / accessibility / content audit followed the conversion. Every fix
below is pixel-neutral — the 60-comparison parity run was re-run afterwards and
still reports 0.000000.

**SEO**

- `metadataBase` set, so `canonical` and `og:url` are absolute. Relative values
  are dropped or mis-resolved by several social scrapers.
- Added `public/og.jpg`, a 1200x630 card built from the real hero photograph and
  Anton letterforms by `scripts/build-og-image.py`. There was no `og:image` at
  all before, so every shared link rendered as a bare text card.
- Added JSON-LD (`lib/structured-data.ts`): `ProfessionalService` with address,
  phone, email, founders and a service catalogue; `WebSite`; and an `ItemList`
  of the four featured projects. A one-page site otherwise gives crawlers
  nothing to resolve the entity against.
- Added `app/sitemap.ts` and `app/robots.ts` (the static `public/robots.txt` had
  no `Sitemap:` directive and would have shadowed the route).
- Replaced the `Lovable App` / `Lovable Generated Project` / `author: Lovable` /
  `twitter:site: @Lovable` placeholders with real values. Those were the 404
  page's title and description.
- Four footer "Services" links pointed at `#top` — four internal links to
  nowhere. They now point at `#services`.
- `fetchPriority="high"` on the hero image, the LCP element on every visit.
- Preloaded `barlow-700`: the About section sets several names in `<strong>`,
  and with `font-display: block` those words stayed invisible after the rest of
  the paragraph had painted.

**Accessibility**

- Added a skip link as the first tab stop. Keyboard and switch users previously
  had to tab the entire fixed masthead on every visit (WCAG 2.4.1).
- Added `autocomplete="name"` / `autocomplete="email"` to the contact form
  (WCAG 1.3.5, AA).
- The three "Learn More" pillar links were indistinguishable in a screen
  reader's link list; each now carries its pillar name as an accessible name.
- "Omaha, NE" was a link to `#top` — an address is not a destination. It is now
  text.
- Added an `aria-live` status region for the form confirmation; the toast alone
  is not reliably announced.
- The form now clears after submit instead of silently re-submitting.

**Content / assets**

- Restored the Heartland Plein Air Festival thumbnail. It had been served from
  Lovable's asset CDN and was never in version control, so it 404'd after the
  migration and the card rendered its error fallback. It is now a committed
  1200x800 capture of the live project.
- Deleted `hero-secondary.jpg`, unreferenced since the hero was rebalanced.

## Hero

The hero is the one place that deliberately diverges from the original render.

It used to be capped at `74vh` (`68vh` at `md`), so 230–280px of the next
section always bled into the first view — the fold landed in the middle of
nothing. It is now `min-h-[100svh]`: `min-h` rather than a fixed height so a
short landscape phone lets the stage grow instead of clipping the CTAs, and
`svh` rather than `vh` so mobile browser chrome cannot make the first view
overflow.

Two things followed from that:

- **The display clamp topped out at `6.25rem`, reached at ~1515px.** On anything
  wider the masthead stopped growing while the stage kept expanding, so it shrank
  into the corner of an ever-larger dark field. The ceiling is now `9rem`, which
  keeps `6.6vw` governing out to ~2180px. The block above it widens to `68rem`
  to hold the longest line (6.4 × font-size) without the nowrap spans spilling.
- **The scrim was crushing the photograph.** Three layers multiply, so the far
  right landed ~51% darkened and the whole lower half was flat black. At 74vh
  that was tolerable; at full height it is most of the stage. The right now
  clears to ~34%, and the bottom fade is confined to the last 28%.

Vertical balance after the change is 213px above the headline / 201px below the
CTAs at 1440x900, and 193/213 at 390x844.

Two things followed from making it full-height:

- **A scroll cue at the base.** A hero that fills the viewport gives no signal
  that the page continues. It is a real link to `#services`, not decoration —
  an affordance that looks clickable but cannot be reached by keyboard is worse
  than none — and it is hidden below 640px of viewport height, where it would
  crowd the CTAs.
- **A mobile crop bias.** A portrait phone crops this landscape frame to roughly
  its middle third, which landed on empty desk; the studio and the people sit
  right of centre. `object-[75%_50%]` up to `md` puts them back in shot.

Note that `tests/hero.config.json` raises `paddingTolerance` from 6 to 8. The H1
is deliberately pulled left by 0.045em (the `.heading-flush` optical kern), so
the spread the test measures against the label/CTA edges scales with type size —
it is intended offset, not drift. The larger ceiling puts the widest configured
viewport at ~5.7px, which sat on the old limit.

## Fonts

Anton and Barlow are self-hosted Latin subsets, preloaded, at
`font-display: swap`. They were originally `block`, which is deterministic for
screenshots but hides text for up to three seconds on a slow connection — and on
this site that is the entire page.

Swapping instead of blocking normally trades invisible text for a reflow. Each
face is therefore paired with a metric-matched fallback in `app/fonts.css`:
`size-adjust`, `ascent-override` and `descent-override` are set so the fallback
occupies the same line box and average advance as the real face, computed by
`scripts/build-font-fallbacks.py`. Re-run it if a font is swapped or resubsetted.
The fallbacks are `local()`-only, so they cost no download and simply do not
apply where those system faces are absent.

Measured with the webfonts stalled three seconds, so the fallback paints first:

| Viewport | With metric matching | Without |
| --- | --- | --- |
| 390px | no text reflow | About paragraph 6 → 5 lines (156 → 130px) |
| 768px | no text reflow | Capabilities paragraph 5 → 4 lines (130 → 104px) |

CLS across the load is 0.0002. The headline's own line width does change on
swap, but its lines are `whitespace-nowrap` blocks, so nothing below them moves.

Screenshot runs stay deterministic because the harness waits on
`document.fonts.ready` and the `data-fonts-ready` flag before capturing.

## Carried-over lint warnings

`npm run lint` reports 0 errors and 11 warnings. They are all patterns carried
over verbatim from the TanStack build — `set-state-in-effect` in the SSR-safe
"sync after mount" hooks, `refs` in FeaturedWork's focus-restore mirror, `purity`
in shadcn's untouched `sidebar.tsx`. `eslint.config.mjs` documents each one.
They are worth revisiting, but the Playwright suite pins the behaviour they
produce, so they are warnings rather than errors.

## Test baselines

`tests/baselines/` still holds the PNGs recorded from the TanStack app on CI
Linux. Keep them: on `ubuntu-latest` they double as a cross-framework pixel
check. They do **not** reproduce on macOS — `scrollbar-gutter: stable` reserves
15px against a classic scrollbar on Linux and 0px against macOS's overlay
scrollbars, so every capture is 15px narrower. The original app fails those same
comparisons on macOS in exactly the same way; run the baseline-backed suites in
CI, and the behavioural ones locally.

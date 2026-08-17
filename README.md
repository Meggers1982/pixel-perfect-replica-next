# Brand Ledger — Next.js

The Brand Ledger one-page site, converted from the Lovable/TanStack Start (Vite)
build to Next.js 16 (App Router, React 19, Tailwind v4).

The render is pixel-identical to the original: every section was screenshotted
at all ten viewports in `tests/hero.config.json` against both apps running side
by side, and all 60 comparisons came back at a **0.000000 diff ratio with no
size mismatches**.

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
advertise the production URL. Everything else lives in `lib/site.ts`.

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

**`og:url` and `canonical` are hand-rendered.** Next resolves relative URLs in
`openGraph.url` and `alternates.canonical` against `metadataBase`, which would
turn `"/"` into an absolute origin-prefixed URL. `tests/head-metadata.expected.json`
is shared with the original app and wants the literal `"/"`, so `lib/seo.ts`
emits those two tags directly. `head-metadata.py` passes all 11 assertions.

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

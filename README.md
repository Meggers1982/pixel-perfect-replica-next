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

## Missing asset

`public/images/heartland-plein-air-arts-festival-website-project.webp` is **not
in this repo**. In the TanStack build it was served from Lovable's asset CDN via
`src/assets/*.asset.json`, so the bytes were never version-controlled.

Until it is exported from Lovable and dropped into `public/images/` under that
exact filename, the first Featured Work card renders `WorkImage`'s "couldn't be
loaded / Retry" fallback and the page logs two 404s. That accounts for every
failure in `footer-work-invalid-slug.py` (console-error assertions) and the
`image alt is ''` failures in `footer-work-history.py`; with a stand-in file in
place, both suites pass completely. Nothing else references it.

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

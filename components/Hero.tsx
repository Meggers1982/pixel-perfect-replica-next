/**
 * Typographic hero: a flat ink field, no photograph.
 *
 * The previous version laid the headline over a stock studio interior and
 * needed three stacked scrim layers to stay legible — a right-to-left ink
 * gradient, a flat wash and a bottom fade — all of which existed only to
 * darken a photograph nobody could really see anyway. Removing the image
 * removes the scrims, removes a 248KB LCP fetch, and lets the Anton headline
 * be the loudest thing on the page, which is the point of the hero.
 *
 * What replaces the photograph is structure rather than decoration: a hairline
 * column grid, an eyebrow, and a red rule marking the break between the
 * headline and the standfirst.
 */
export function Hero() {
  return (
    <section id="top" className="relative">
      {/* `min-h` rather than a fixed height, so a short landscape phone lets the
          stage grow instead of clipping the CTAs; `svh` rather than `vh`, so
          mobile browser chrome cannot make the first view overflow and jump. */}
      <div className="relative flex min-h-[100svh] w-full overflow-hidden bg-ink">
        {/* Hairline column grid. Decorative, and faint enough that it reads as
            paper rule rather than as a table — it gives the empty right half a
            measure without competing with the type. */}
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 hidden md:block"
          style={{
            backgroundImage:
              "repeating-linear-gradient(to right, color-mix(in oklab, var(--cream) 7%, transparent) 0 1px, transparent 1px 12.5%)",
          }}
        />

        {/* pb-20 from the height where the cue appears, so it has its own band
            and cannot land on the CTA row. Reserving it unconditionally instead
            grew the stage past the viewport on phones and pushed the cue below
            the fold, which is worse than not drawing it. */}
        <div className="relative z-10 flex w-full items-center px-5 pb-12 pt-24 [@media(min-height:780px)]:pb-20 sm:px-8 sm:pt-28 lg:pt-32">
          <div className="mx-auto w-full max-w-[1600px]">
            {/* Wide enough to hold the longest line at the upper bound of the
                clamp, so the nowrap spans never spill the block. "Experienced
                by people." sets that bound at 8.83 x font-size — 1271px at the
                9rem ceiling — which is what 82rem leaves room for. 68rem used
                to be enough when the third line read "Read by people."; it is
                not any more, and the overflow was being silently clipped by
                the stage's overflow-hidden rather than showing as a scrollbar. */}
            <div className="max-w-[82rem]">
              <p className="label-caps text-accent-on-dark">
                Content · Design · Search — Omaha, Nebraska
              </p>
              {/* Two size ramps, because the two layouts have different limits.
              
                  Below md the spans wrap, so the binding constraint is the
                  longest *word*: "EXPERIENCED" measures 4.77x the font size, and
                  at a 320px viewport (280px of measure) that caps it near 58px.
                  There was headroom over the old flat 2.6rem, but spending it as
                  a flat floor made small phones worse — the headline is four rows
                  tall there, so every extra pixel pushes the CTAs further below
                  the fold, and at 320x568 and 360x640 they already sit under it.
                  12.2vw instead means the smallest phones keep 2.6rem exactly
                  while a 393px phone gets ~48px and a 430px one ~52px, capped at
                  3.3rem so a large phone in landscape does not run away with it.
              
                  From md the spans are nowrap and the constraint is the longest
                  *line* at 8.83x, which is what the 6.6vw ramp and its 9rem
                  ceiling are sized for. The ceiling is reached at ~2180px; the
                  old 6.25rem one was hit at ~1515px, above which the masthead
                  shrank into the corner of an ever-larger dark field. */}
              <h1
                className="display mt-6 text-[clamp(2.6rem,12.2vw,3.3rem)] leading-[1.04] text-cream [&>span]:block md:text-[clamp(2.6rem,6.6vw,9rem)] md:leading-[0.93] md:[&>span]:whitespace-nowrap"
                style={{
                  marginLeft: "-0.045em",
                  paddingTop: "0.02em",
                  paddingBottom: "0.04em",
                }}
              >
                <span>Found by search.</span>
                <span>Quoted by AI.</span>
                <span>Experienced by people.</span>
              </h1>
              {/* The one piece of brand red above the fold: it marks the break
                  between the claim and the explanation. */}
              <div aria-hidden="true" className="mt-8 h-[6px] w-24 bg-accent" />
              <p
                className="label-caps mt-6 max-w-2xl leading-[1.9] text-cream"
                style={{ letterSpacing: "0.18em" }}
              >
                Brand Ledger is a content, design and search studio in Omaha. We decide what a site
                has to say, design how it works, and make sure both people and AI can find it.
              </p>
              <div className="mt-8 flex flex-col gap-3 sm:flex-row sm:flex-wrap">
                <a
                  href="#contact"
                  className="label-caps inline-flex w-full max-w-xs items-center justify-center bg-cream px-7 py-4 text-ink transition-opacity hover:opacity-85 sm:w-auto sm:max-w-none sm:justify-start"
                >
                  Start a Project
                </a>
                <a
                  href="#work"
                  className="label-caps inline-flex w-full max-w-xs items-center justify-center border border-cream px-7 py-4 text-cream transition-colors hover:bg-cream hover:text-ink sm:w-auto sm:max-w-none sm:justify-start"
                >
                  See the Work
                </a>
              </div>
            </div>
          </div>
        </div>

        {/* A full-height hero gives no visual signal that the page continues,
            so mark the edge. It is a real link rather than decoration: an
            affordance that looks clickable but cannot be reached by keyboard
            is worse than none.
            
            The threshold is 780px rather than 640px because the headline now
            wraps to four rows on a phone: below that the hero is taller than
            the viewport, so the cue rendered either on top of the CTAs or
            below the fold. On those viewports the CTA row already sits at the
            bottom edge, which signals the same thing without a label. */}
        <a
          href="#services"
          aria-label="Scroll to services"
          className="group absolute inset-x-0 bottom-0 z-10 hidden [@media(min-height:780px)]:block"
        >
          <span className="mx-auto flex max-w-[1600px] items-center gap-3 px-5 pb-8 sm:px-8 sm:pb-10">
            <span className="label-caps text-cream/70 transition-colors group-hover:text-cream">
              Scroll
            </span>
            <svg
              aria-hidden="true"
              viewBox="0 0 12 20"
              className="scroll-cue h-5 w-3 text-cream/70 transition-colors group-hover:text-cream"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
            >
              <path d="M6 0v18M1 13l5 5 5-5" />
            </svg>
          </span>
        </a>
      </div>
    </section>
  );
}

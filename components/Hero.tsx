// Plain <img> against /public: the scrim and object-cover crop do all the work,
// so next/image's srcset/sizes rewriting would only risk shifting the render.
const heroImage = "/images/hero.jpg";

export function Hero() {
  return (
    <section id="top" className="relative">
      {/* Hero stage: full-bleed image with headline, description and CTAs overlaid.
          `min-h` rather than a fixed height, so a short landscape phone lets the
          stage grow instead of clipping the CTAs; `svh` rather than `vh`, so
          mobile browser chrome cannot make the first view overflow and jump. */}
      <div className="relative flex min-h-[100svh] w-full overflow-hidden">
        <img
          src={heroImage}
          alt="Brand Ledger designers reviewing page layouts and content plans in the studio"
          width={1600}
          height={1100}
          // The LCP element on every visit: fetch it ahead of the lazy pillars.
          fetchPriority="high"
          // A portrait phone crops this landscape frame to roughly its middle
          // third, which lands on empty desk — the studio and the people sit
          // right of centre. Bias the crop there until the viewport is wide
          // enough to show them anyway.
          className="absolute inset-0 h-full w-full object-cover object-[75%_50%] md:object-center"
        />
        {/* Scrim: directional wash that stays dense behind the copy on the left
            and clears toward the right so the photograph reads. The three layers
            multiply, so the far right used to land ~51% darkened and the whole
            lower third was crushed to flat black — at full height that dead band
            is most of the stage. The right now clears to ~34% and the bottom fade
            is confined to the last 28%, where it resolves into solid ink so the
            hero meets the ink section below without a seam. */}
        <div className="absolute inset-0 bg-ink/50 md:bg-ink/25" />
        {/* Pixel stops, not percentages. The copy column is width-capped
            (max-w-2xl), but a percentage-based wash clears at a fixed fraction
            of the viewport — so around 812px the standfirst ran past the dense
            zone onto a lit window and measured 4.16:1, under AA for 11.5px
            text. Anchoring the stops in px keeps the dense zone over the copy
            at every width while still clearing for the photograph on wide
            screens. */}
        <div
          className="absolute inset-0"
          style={{
            backgroundImage: [
              "linear-gradient(to right,",
              "color-mix(in oklab, var(--ink) 92%, transparent) 0px,",
              "color-mix(in oklab, var(--ink) 78%, transparent) 780px,",
              "color-mix(in oklab, var(--ink) 12%, transparent) 1500px)",
            ].join(" "),
          }}
        />
        <div className="absolute inset-0 bg-gradient-to-t from-ink from-0% via-transparent via-28% to-transparent" />

        <div className="relative z-10 flex w-full items-center px-5 pb-12 pt-24 sm:px-8 sm:pt-28 lg:pt-32">
          <div className="mx-auto w-full max-w-[1600px]">
            {/* Wide enough to hold the longest line at the new upper bound
                (6.4 x font-size), so the nowrap spans never spill the block. */}
            <div className="max-w-[68rem]">
            <h1
              className="display text-cream [&>span]:block [&>span]:whitespace-nowrap"
              style={{
                // The old 6.25rem ceiling was reached at ~1515px, so on anything
                // wider the masthead stopped growing and shrank into the corner
                // of an ever-larger dark field. 6.6vw now runs to ~2180px.
                fontSize: "clamp(2.6rem, 6.6vw, 9rem)",
                marginLeft: "-0.045em",
                paddingTop: "0.02em",
                paddingBottom: "0.04em",
              }}
            >
              <span>Found by search.</span>
              <span>Quoted by AI.</span>
              <span>Read by people.</span>
            </h1>
            <p
              className="label-caps mt-6 max-w-2xl leading-[1.9] text-cream"
              style={{ letterSpacing: "0.18em" }}
            >
              Brand Ledger is a content, design and search studio in Omaha. We decide what a site has
              to say, design how it works, and make sure both people and AI can find it.
            </p>
            <div className="mt-7 flex flex-col gap-3 sm:flex-row sm:flex-wrap">
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
            is worse than none. Hidden on short viewports, where it would
            crowd the CTAs. */}
        <a
          href="#services"
          aria-label="Scroll to services"
          className="group absolute inset-x-0 bottom-0 z-10 hidden [@media(min-height:640px)]:block"
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

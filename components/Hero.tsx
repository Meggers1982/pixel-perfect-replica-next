// Plain <img> against /public: the scrim and object-cover crop do all the work,
// so next/image's srcset/sizes rewriting would only risk shifting the render.
const heroImage = "/images/hero.jpg";

export function Hero() {
  return (
    <section id="top" className="relative">
      {/* Hero stage: full-bleed image with headline, description and CTAs overlaid. */}
      <div className="relative flex min-h-[78vh] w-full overflow-hidden md:h-[68vh] md:min-h-[480px] lg:h-[74vh] lg:min-h-[560px]">
        <img
          src={heroImage}
          alt="Brand Ledger designers reviewing printed brand work in the studio"
          width={1600}
          height={1100}
          // The LCP element on every visit: fetch it ahead of the lazy pillars.
          fetchPriority="high"
          className="absolute inset-0 h-full w-full object-cover"
        />
        {/* Scrim: directional wash that stays dense behind the copy on the left
            and clears toward the right so the photograph reads. */}
        <div className="absolute inset-0 bg-ink/60 md:bg-ink/30" />
        <div className="absolute inset-0 bg-gradient-to-r from-ink/92 via-ink/75 to-ink/30" />
        <div className="absolute inset-0 bg-gradient-to-t from-ink/70 via-transparent to-ink/45" />

        <div className="relative z-10 flex w-full items-center px-5 pb-12 pt-24 sm:px-8 sm:pt-28 lg:pt-32">
          <div className="mx-auto w-full max-w-[1600px]">
            <div className="max-w-[54rem]">
            <h1
              className="display text-cream [&>span]:block [&>span]:whitespace-nowrap"
              style={{
                fontSize: "clamp(2.6rem, 6.6vw, 6.25rem)",
                marginLeft: "-0.045em",
                paddingTop: "0.02em",
                paddingBottom: "0.04em",
              }}
            >
              <span>We build brands</span>
              <span>that behave</span>
              <span>like businesses</span>
            </h1>
            <p
              className="label-caps mt-6 max-w-2xl leading-[1.9] text-cream"
              style={{ letterSpacing: "0.18em" }}
            >
              Brand Ledger is a nine-person studio in Omaha working with founder-led consumer and
              healthcare companies from first positioning through launch.
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
      </div>
    </section>
  );
}

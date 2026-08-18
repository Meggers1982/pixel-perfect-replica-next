/**
 * Service pillars as designed panels rather than photographs.
 *
 * Each pillar used to sit on a stock photograph under a 60% ink wash — dark
 * enough that the image was texture, not information, and in a palette (teal,
 * orange, yellow) that shares nothing with cream/ink/red. The alt text had
 * also drifted: it described page briefs and workshop walls that were not in
 * the frames.
 *
 * The replacement is built from the same parts as the rest of the site: an
 * oversized ghost numeral, a hairline index rule, and a red mark under the
 * headline. It is on-palette by construction, carries no image weight, and
 * needs no alt text because there is nothing to describe — the numeral is
 * decorative and the heading already names the pillar.
 */
const pillars = [
  {
    number: "01",
    name: "Content Strategy & SEO",
    copy: "Content audit, message hierarchy, sitemap and a brief for every page — what it says, who it is for, and what it should make someone do. Search engine optimization shapes the structure from the start, so ranking is not something bolted on after launch.",
    target: "#capabilities",
  },
  {
    number: "02",
    name: "Web & UX Design",
    copy: "Layout, type, navigation and the order a visitor makes decisions in. We prototype in the browser with your real content, so choices get made against real text at real widths, not lorem ipsum in a static comp.",
    target: "#work",
  },
  {
    number: "03",
    name: "AI & GEO",
    copy: "Search is turning into answers, so generative engine optimization (GEO) is now its own discipline. We structure content so models can parse and cite it — clean semantics, schema, and pages that state a claim plainly instead of burying it in preamble. If an AI cannot quote you, it will quote a competitor.",
    target: "#about",
  },
];

export function ServicePillars() {
  return (
    <section id="services" className="border-t border-cream/25 bg-ink">
      {pillars.map((pillar, index) => {
        const alignRight = index % 2 === 1;
        return (
          <article
            key={pillar.name}
            className="relative isolate min-h-[70vh] overflow-hidden border-t border-cream/25 first:border-t-0"
          >
            {/* Ghost numeral: bled off the outer edge so it reads as a printed
                folio mark rather than a centred graphic. Decorative only — the
                same number is announced in the index rule below. */}
            <span
              aria-hidden="true"
              className={`display pointer-events-none absolute -bottom-[0.22em] select-none leading-none text-cream/[0.055] ${
                alignRight ? "-left-[0.06em]" : "-right-[0.06em]"
              }`}
              style={{ fontSize: "clamp(12rem, 30vw, 30rem)" }}
            >
              {pillar.number}
            </span>

            <div
              className={`relative mx-auto flex min-h-[70vh] max-w-[1600px] flex-col justify-between px-5 py-16 sm:px-8 ${
                alignRight ? "md:items-end md:text-right" : ""
              }`}
            >
              {/* Index rule: the numeral, then a hairline running to the far
                  edge of the measure. Mirrored on the right-aligned panels so
                  the rule always runs away from the type, not into it. */}
              <div
                className={`flex w-full items-center gap-5 ${alignRight ? "flex-row-reverse" : ""}`}
              >
                <span className="label-caps text-accent-on-dark">{pillar.number}</span>
                <span aria-hidden="true" className="h-px flex-1 bg-cream/20" />
              </div>

              <div className={`mt-16 flex flex-col ${alignRight ? "md:items-end" : ""}`}>
                <h2
                  className="display heading-flush max-w-[14ch] break-words text-cream"
                  style={{ fontSize: "clamp(2.25rem, 6vw, 5.5rem)" }}
                >
                  {pillar.name}
                </h2>

                <div aria-hidden="true" className="mt-7 h-[6px] w-16 bg-accent" />

                <p className="mt-6 max-w-2xl text-base leading-relaxed text-cream/90">
                  {pillar.copy}
                </p>
                {/* Three links reading only "Learn More" are indistinguishable in
                    a screen reader's link list — name each by its pillar. */}
                <a
                  href={pillar.target}
                  aria-label={`Learn more about ${pillar.name}`}
                  className="label-caps mt-8 inline-flex w-fit items-center border border-cream px-7 py-4 text-cream transition-colors hover:bg-cream hover:text-ink"
                >
                  Learn More
                </a>
              </div>
            </div>
          </article>
        );
      })}
    </section>
  );
}

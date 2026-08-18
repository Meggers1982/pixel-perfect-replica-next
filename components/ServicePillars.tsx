const brandImage = "/images/pillar-brand.jpg";
const digitalImage = "/images/pillar-digital.jpg";
const strategyImage = "/images/pillar-strategy.jpg";

const pillars = [
  {
    name: "Content Strategy & SEO",
    image: brandImage,
    alt: "A content plan and page briefs laid out in print on a studio table",
    copy: "Content audit, message hierarchy, sitemap and a brief for every page — what it says, who it is for, and what it should make someone do. Search engine optimization shapes the structure from the start, so ranking is not something bolted on after launch.",
    target: "#capabilities",
  },
  {
    name: "Web & UX Design",
    image: digitalImage,
    alt: "A website layout displayed on a laptop in a dim studio",
    copy: "Layout, type, navigation and the order a visitor makes decisions in. We prototype in the browser with your real content, so choices get made against real text at real widths, not lorem ipsum in a static comp.",
    target: "#work",
  },
  {
    name: "AI & GEO",
    image: strategyImage,
    alt: "A strategy workshop wall covered in notes and printed charts",
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
            <img
              src={pillar.image}
              alt={pillar.alt}
              width={1600}
              height={900}
              loading="lazy"
              className="absolute inset-0 -z-10 h-full w-full object-cover"
            />
            <div className="absolute inset-0 -z-10 bg-ink/60" />
            <div
              className={`mx-auto flex min-h-[70vh] max-w-[1600px] flex-col justify-end px-5 py-16 sm:px-8 ${
                alignRight ? "md:items-end md:text-right" : ""
              }`}
            >
              <h2
                className="display heading-flush max-w-[14ch] break-words text-cream"
                style={{ fontSize: "clamp(2.25rem, 6vw, 5.5rem)" }}
              >
                {pillar.name}
              </h2>

              <p className="mt-6 max-w-2xl text-base leading-relaxed text-cream/90">{pillar.copy}</p>
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
          </article>
        );
      })}
    </section>
  );
}

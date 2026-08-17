const brandImage = "/images/pillar-brand.jpg";
const digitalImage = "/images/pillar-digital.jpg";
const strategyImage = "/images/pillar-strategy.jpg";

const pillars = [
  {
    name: "Brand Identity",
    image: brandImage,
    alt: "Embossed logotype on printed brand collateral",
    copy: "Naming, logotype, typography, packaging and the full system of rules that keeps it coherent after we hand it over. Every identity ships with a written playbook and production-ready files.",
    target: "#work",
  },
  {
    name: "Digital Product",
    image: digitalImage,
    alt: "A website layout displayed on a laptop in a dim studio",
    copy: "Marketing sites, storefronts and product interfaces designed and built in-house. We prototype in the browser early so decisions are made against real behavior, not static comps.",
    target: "#capabilities",
  },
  {
    name: "Positioning & Strategy",
    image: strategyImage,
    alt: "A strategy workshop wall covered in notes and printed charts",
    copy: "Category research, customer interviews, messaging hierarchy and go-to-market narrative. The output is a decision document your team can argue with, not a deck that sits unopened.",
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

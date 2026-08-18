const capabilities = [
  {
    step: "01",
    title: "Audit",
    copy: "Two weeks with your analytics, your search data, your visibility in AI answers and your customers. We come back with what the site is failing to say, stated plainly, in one page.",
  },
  {
    step: "02",
    title: "Plan",
    copy: "Sitemap, message hierarchy and a brief for every page. Written first, designed second — if the sentence doesn't hold up in plain text, no typeface will save it.",
  },
  {
    step: "03",
    title: "Design & Build",
    copy: "Interface and layout produced in tight weekly cycles, with your real content in it rather than placeholder text, and the founders in the room instead of a review queue.",
  },
  {
    step: "04",
    title: "Launch & Measure",
    copy: "Launch, then track what it actually earned — rankings, citations in AI answers, and what people do once they arrive. Six-month support window so the system survives contact with your team.",
  },
];

export function Capabilities() {
  return (
    <section id="capabilities" className="bg-ink py-24 sm:py-32">
      <div className="mx-auto max-w-[1600px] px-5 sm:px-8">
        <div className="max-w-3xl">
          <h2
            className="display section-title heading-flush break-words text-cream"
          >
            How We Work
          </h2>
        </div>

        <ol className="mt-12 border-t border-cream/25">
          {capabilities.map((item) => (
            <li
              key={item.step}
              // items-baseline lined the three columns up on their baselines,
              // which for type this mismatched in size meant three different
              // starting heights: the number's cap-top sat 18px above the
              // title's and the copy's sat 19px below it. items-start puts the
              // number and title cap-tops within 1px of each other (Anton's
              // 0.93 line-height leaves almost no half-leading above the caps).
              className="grid gap-4 border-b border-cream/25 py-8 md:grid-cols-[120px_260px_1fr] md:items-start md:gap-10"
            >
              <span
                className="display text-accent-on-dark"
                style={{ fontSize: "clamp(2rem, 4vw, 3.5rem)" }}
              >
                {item.step}
              </span>
              <h3
                className="display text-cream"
                style={{ fontSize: "clamp(1.5rem, 2.6vw, 2.25rem)" }}
              >
                {item.title}
              </h3>
              {/* Barlow at leading-relaxed carries ~7.4px of half-leading above
                  its cap-height, so aligning the boxes still leaves the copy
                  sitting low. 0.46em of its own size trims exactly that, which
                  holds at every breakpoint because this column's type size is
                  fixed. Only from md, where the columns are actually side by
                  side — stacked, it would just eat the row gap. */}
              <p className="max-w-2xl text-base leading-relaxed text-cream/85 md:-mt-[0.46em]">
                {item.copy}
              </p>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}

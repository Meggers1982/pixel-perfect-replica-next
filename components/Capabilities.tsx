const capabilities = [
  {
    step: "01",
    title: "Diagnose",
    copy: "Two weeks of interviews, category audit and internal stakeholder sessions. We come back with the problem stated plainly, in one page.",
  },
  {
    step: "02",
    title: "Position",
    copy: "Messaging hierarchy, naming and narrative. Written first, designed second — if the sentence doesn't hold up in plain text, no typeface will save it.",
  },
  {
    step: "03",
    title: "Design",
    copy: "Identity systems, packaging and interface design produced in tight weekly cycles with the founders in the room, not in a review queue.",
  },
  {
    step: "04",
    title: "Ship & Support",
    copy: "Production files, build, launch and a six-month support window so the system survives contact with your team.",
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
              className="grid gap-4 border-b border-cream/25 py-8 md:grid-cols-[120px_260px_1fr] md:items-baseline md:gap-10"
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
              <p className="max-w-2xl text-base leading-relaxed text-cream/85">{item.copy}</p>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}

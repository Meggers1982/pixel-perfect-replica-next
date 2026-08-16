export function About() {
  return (
    <section id="about" className="border-t-2 border-ink bg-cream py-20 sm:py-28">
      <div className="mx-auto grid max-w-[1600px] gap-12 px-5 sm:px-8 lg:grid-cols-[1fr_1.2fr]">
        <div>
          <h2
            className="display section-title heading-flush break-words text-accent"
          >
            Nine people, no account layer
          </h2>
        </div>

        <div className="space-y-6 text-base leading-relaxed text-ink/80">
          <p>
            Brand Ledger was founded in 2014 by <strong className="text-ink">Dana Whitcomb</strong>{" "}
            and <strong className="text-ink">Elias Roche</strong> after a decade between{" "}
            <strong className="text-ink">Pentagram</strong> and{" "}
            <strong className="text-ink">Wolff Olins</strong>. The studio has stayed deliberately
            small: the people you meet in the first call are the people who do the work.
          </p>
          <p>
            We take on eight to ten engagements a year, mostly with founder-led consumer and
            healthcare companies between Series A and Series C. Recent partners include{" "}
            <strong className="text-ink">Hollow Roasters</strong>,{" "}
            <strong className="text-ink">Field &amp; Frame</strong>,{" "}
            <strong className="text-ink">Meridian Health</strong> and{" "}
            <strong className="text-ink">Cascade Outfitters</strong>.
          </p>
          <p>
            Work from the studio has been recognized by{" "}
            <strong className="text-ink">D&amp;AD</strong>,{" "}
            <strong className="text-ink">The One Show</strong> and{" "}
            <strong className="text-ink">Communication Arts</strong>, though we would rather be
            judged on what happened to the businesses afterward.
          </p>
        </div>
      </div>
    </section>
  );
}

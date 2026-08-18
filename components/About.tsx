export function About() {
  return (
    <section id="about" className="border-t-2 border-ink bg-cream py-20 sm:py-28">
      <div className="mx-auto grid max-w-[1600px] gap-12 px-5 sm:px-8 lg:grid-cols-[1fr_1.2fr]">
        <div>
          <h2 className="display section-title heading-flush break-words text-accent">
            No account layer
          </h2>
        </div>

        <div className="space-y-6 text-base leading-relaxed text-ink/80">
          <p>
            Brand Ledger is the studio of <strong className="text-ink">Meagan Morris</strong>. You
            talk to the person doing the work — there is no manager relaying it, and nothing gets
            decided by someone who wasn&apos;t in the room.
          </p>
          <p>
            The studio takes on a small number of engagements at a time, and still covers the
            ground it does because the research is{' '}
            <strong className="text-ink">systematic rather than sampled</strong> — an entire
            category crawled, ten thousand search queries read, the twentieth variation of a page
            drafted before one is chosen. The gathering scales. The judgement about what any of it
            means does not.
          </p>
          <p>
            We would rather be judged on what happened afterward — the rankings, the citations, the
            pipeline — than on how the site looked the week it launched.
          </p>
        </div>
      </div>
    </section>
  );
}

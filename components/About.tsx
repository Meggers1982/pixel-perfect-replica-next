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
            Brand Ledger was founded in 2014 by <strong className="text-ink">Dana Whitcomb</strong>{" "}
            and <strong className="text-ink">Elias Roche</strong>. The studio has stayed
            deliberately small: the people you meet on the first call are the people who do the
            work, and nothing gets relayed through someone who wasn&apos;t in the room.
          </p>
          <p>
            We take on eight to ten engagements a year. A studio this size can cover that much
            ground because <strong className="text-ink">AI does the parts that scale</strong> —
            crawling a category, reading ten thousand search queries, drafting the twentieth
            variation of a page — while the judgement about what any of it means stays with us. The
            research is machine-assisted. The decisions are not.
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

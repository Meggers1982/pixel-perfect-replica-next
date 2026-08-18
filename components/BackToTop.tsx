"use client";

import { useEffect, useState } from "react";

/**
 * Back-to-top affordance, built as the mirror of the hero's scroll cue: the
 * same label-caps + thin stroked arrow, pointing the other way.
 *
 * A real <a href="#top"> rather than a scripted button, for the same reason
 * the scroll cue is one — it works without JS, it is keyboard reachable, and
 * html { scroll-behavior: smooth } already animates the trip (and is disabled
 * under prefers-reduced-motion by the base layer).
 *
 * Unlike the hero cue this does not animate on a loop. That cue is a one-time
 * hint on first paint; a control pinned to the viewport for the whole page
 * would just be movement in the corner of the eye, so the nudge is on hover
 * and focus only.
 *
 * It carries its own ink chip because the page runs cream -> ink -> red behind
 * it: cream-on-transparent would vanish over the About section.
 */
export function BackToTop() {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    // Show once the hero is behind you — roughly the point where "back to top"
    // starts meaning something.
    const onScroll = () => setVisible(window.scrollY > window.innerHeight * 0.9);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    return () => {
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
    };
  }, []);

  // Unmounted rather than hidden: a visually hidden control that still takes a
  // tab stop is worse than no control.
  if (!visible) return null;

  return (
    <a
      href="#top"
      aria-label="Back to top"
      className="group fixed right-5 z-40 inline-flex min-h-11 items-center gap-3 border border-cream/30 bg-ink px-4 py-3 text-cream/80 transition-colors hover:border-cream hover:text-cream focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent sm:right-8"
      // Sits above the cookie bar while it is on screen; CookieBar publishes its
      // own height so this never has to guess or hard-code it.
      style={{ bottom: "calc(1.5rem + var(--cookie-bar-height, 0px))" }}
    >
      <span className="label-caps">Top</span>
      <svg
        aria-hidden="true"
        viewBox="0 0 12 20"
        className="h-5 w-3 transition-transform group-hover:-translate-y-1 group-focus-visible:-translate-y-1 motion-reduce:transform-none"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
      >
        <path d="M6 20V2M1 7l5-5 5 5" />
      </svg>
    </a>
  );
}

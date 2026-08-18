"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import { useSearchParams } from "next/navigation";
import { ArrowLeft, ArrowRight, X } from "lucide-react";

import { prefetchImage, prefetchImagesWhenIdle } from "@/lib/image-prefetch";
import { logPerf, now } from "@/lib/perf-log";
import { projects } from "@/lib/projects";
import { useReducedData } from "@/lib/use-reduced-data";
import { useReducedMotion } from "@/lib/use-reduced-motion";
import { WorkImage } from "@/components/WorkImage";

const SWIPE_THRESHOLD = 48;
const LIGHTBOX_FOCUSABLE = 'button:not([disabled]), a[href], [tabindex]:not([tabindex="-1"])';

/**
 * The open project lives in `?work=<slug>`, matching the footer's deep links.
 *
 * Reads go through useSearchParams(); writes go through the History API rather
 * than router.push/replace. Next patches pushState/replaceState and feeds them
 * back into useSearchParams(), so the lightbox opens with no RSC round trip and
 * no scroll side effects, while back/forward still walk the same stack the
 * TanStack `navigate({ search: { work } })` calls built.
 */
function setWorkParam(slug: string | null, replace: boolean) {
  const url = slug ? `/?work=${encodeURIComponent(slug)}#work` : "/#work";
  if (replace) window.history.replaceState(null, "", url);
  else window.history.pushState(null, "", url);
}

export function FeaturedWork() {
  const searchParams = useSearchParams();
  const workParam = searchParams.get("work");
  const cardRefs = useRef<Array<HTMLButtonElement | null>>([]);
  const trackRef = useRef<HTMLDivElement>(null);
  const contentRef = useRef<HTMLDivElement>(null);
  const [slide, setSlide] = useState(0);
  const touchStart = useRef<{ x: number; y: number } | null>(null);

  const reducedMotion = useReducedMotion();
  const { reducedData, mode } = useReducedData();
  const motionClasses = reducedMotion
    ? "transition-none"
    : "data-[state=closed]:animate-out data-[state=open]:animate-in data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0";

  const slugIndex = projects.findIndex((p) => p.slug === workParam);
  const openIndex = slugIndex === -1 ? null : slugIndex;
  const isOpen = openIndex !== null;
  const active = isOpen ? projects[openIndex] : null;

  const openIndexRef = useRef(0);
  if (openIndex !== null) openIndexRef.current = openIndex;

  const openAt = useCallback((index: number, replace = false) => {
    const project = projects[index];
    if (!project) return;
    setWorkParam(project.slug, replace);
  }, []);

  const close = useCallback(() => {
    setWorkParam(null, false);
  }, []);

  // Deep link to an unknown slug: render the section normally (no lightbox) and
  // strip the stale ?work param so the URL reflects what is actually shown.
  useEffect(() => {
    if (workParam === null || slugIndex !== -1) return;
    setWorkParam(null, true);
  }, [workParam, slugIndex]);

  // Radix keeps the dialog mounted for the length of its exit animation. A
  // history step that closes and immediately reopens the lightbox therefore
  // reuses the same node, so the focus scope never remounts and Radix's own
  // open-autofocus never fires again — leaving focus stranded on <body>.
  // Re-assert it here, but only on a closed -> open edge, so stepping between
  // projects still leaves focus on whichever arrow the visitor pressed.
  useEffect(() => {
    if (!isOpen) return;
    const frame = requestAnimationFrame(() => {
      const node = contentRef.current;
      if (!node || node.contains(document.activeElement)) return;
      const target = node.querySelector<HTMLElement>(LIGHTBOX_FOCUSABLE) ?? node;
      target.focus({ preventScroll: true });
    });
    return () => cancelAnimationFrame(frame);
  }, [isOpen]);

  const step = useCallback(
    (delta: number) => {
      if (openIndex === null) return;
      openAt((openIndex + delta + projects.length) % projects.length, true);
    },
    [openAt, openIndex],
  );

  useEffect(() => {
    if (!isOpen) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "ArrowRight") step(1);
      if (event.key === "ArrowLeft") step(-1);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [isOpen, step]);

  const prevProject = isOpen ? projects[(openIndex + projects.length - 1) % projects.length] : null;
  const nextProject = isOpen ? projects[(openIndex + 1) % projects.length] : null;

  // Optional background warm-up: full-size lightbox images fetched while idle.
  // Skipped entirely in reduced-data mode (Save-Data, 2G, offline).
  useEffect(() => {
    if (reducedData) return;
    return prefetchImagesWhenIdle(projects.map((p) => p.image));
  }, [reducedData]);

  // Keep the neighbouring slides ready while the lightbox is open — but only
  // the visible one is fetched when the visitor asked us to save data.
  useEffect(() => {
    if (!isOpen) return;
    if (active) void prefetchImage(active.image, { force: true });
    if (reducedData) {
      logPerf({ name: "neighbours:skipped", slug: active?.slug, detail: { reason: mode.reason } });
      return;
    }
    if (prevProject) void prefetchImage(prevProject.image);
    if (nextProject) void prefetchImage(nextProject.image);
  }, [isOpen, active, prevProject, nextProject, reducedData, mode.reason]);

  // Section mount = first thumbnail paint opportunity.
  useEffect(() => {
    logPerf({
      name: "thumbnail:render",
      at: now(),
      detail: { count: projects.length, reducedData, network: mode.reason },
    });
  }, [reducedData, mode.reason]);

  // Lightbox open timing, per project.
  useEffect(() => {
    if (!active) return;
    logPerf({ name: "lightbox:open", slug: active.slug, detail: { reducedData } });
  }, [active, reducedData]);

  // Deep-link on a hard refresh: align the underlying carousel with the open
  // project so closing restores focus to a card already in view (no jump).
  const alignedOnMount = useRef(false);
  useEffect(() => {
    if (alignedOnMount.current || openIndex === null) return;
    alignedOnMount.current = true;
    cardRefs.current[openIndex]?.scrollIntoView({
      block: "nearest",
      inline: "start",
      behavior: "auto",
    });
  }, [openIndex]);

  const warm = useCallback(
    (src: string) => {
      if (reducedData) return;
      void prefetchImage(src);
    },
    [reducedData],
  );

  // Mobile carousel: exactly one card per view, stepped with arrows.
  // Wraps around at both ends so the arrows are never dead ends.
  // Positions come from bounding rects so the maths holds in RTL, where
  // scrollLeft runs negative and offsetLeft no longer tracks scroll order.
  const scrollToCard = useCallback(
    (index: number) => {
      const track = trackRef.current;
      const wrapped = (index + projects.length) % projects.length;
      const card = track?.children[wrapped] as HTMLElement | undefined;
      if (!track || !card) return;
      setSlide(wrapped);
      const delta = card.getBoundingClientRect().left - track.getBoundingClientRect().left;
      track.scrollTo({
        left: track.scrollLeft + delta,
        behavior: reducedMotion ? "auto" : "smooth",
      });
    },
    [reducedMotion],
  );

  const onTrackScroll = useCallback(() => {
    const track = trackRef.current;
    if (!track) return;
    const trackLeft = track.getBoundingClientRect().left;
    const children = Array.from(track.children) as HTMLElement[];
    let nearest = 0;
    let best = Infinity;
    children.forEach((child, index) => {
      const distance = Math.abs(child.getBoundingClientRect().left - trackLeft);
      if (distance < best) {
        best = distance;
        nearest = index;
      }
    });
    setSlide(nearest);
  }, []);

  // In RTL the visual axis is mirrored: swiping/arrowing "right" must step
  // backwards through the projects, while logical prev/next buttons stay as-is.
  const directionFactor = useCallback(() => {
    const track = trackRef.current;
    if (!track || typeof window === "undefined") return 1;
    return window.getComputedStyle(track).direction === "rtl" ? -1 : 1;
  }, []);

  // Left/right arrow keys step the carousel whenever focus is inside it.
  const onTrackKeyDown = useCallback(
    (event: React.KeyboardEvent) => {
      if (isOpen) return;
      if (event.key !== "ArrowRight" && event.key !== "ArrowLeft") return;
      event.preventDefault();
      const step = (event.key === "ArrowRight" ? 1 : -1) * directionFactor();
      scrollToCard(slide + step);
    },
    [directionFactor, isOpen, scrollToCard, slide],
  );

  // Touch swipe on the track itself. Native snap-scrolling already handles most
  // drags; this only kicks in when the finger moved but the track did not
  // (short flicks, snap points that never engaged), so arrows and keyboard
  // navigation keep working untouched.
  const trackTouch = useRef<{ x: number; y: number; scrollLeft: number } | null>(null);

  const onTrackTouchStart = useCallback((event: React.TouchEvent) => {
    const touch = event.touches[0];
    const track = trackRef.current;
    trackTouch.current =
      touch && track ? { x: touch.clientX, y: touch.clientY, scrollLeft: track.scrollLeft } : null;
  }, []);

  const onTrackTouchEnd = useCallback(
    (event: React.TouchEvent) => {
      const start = trackTouch.current;
      trackTouch.current = null;
      const track = trackRef.current;
      if (!start || !track) return;
      const touch = event.changedTouches[0];
      if (!touch) return;
      const dx = touch.clientX - start.x;
      const dy = touch.clientY - start.y;
      if (Math.abs(dx) < SWIPE_THRESHOLD || Math.abs(dx) < Math.abs(dy) * 1.5) return;
      if (Math.abs(track.scrollLeft - start.scrollLeft) > 8) return; // native scroll won
      scrollToCard(slide + (dx < 0 ? 1 : -1) * directionFactor());
    },
    [directionFactor, scrollToCard, slide],
  );

  // With a single project there is nothing to step between: the arrows would
  // wrap to the same card and the counter would read 01 / 01.
  const steppable = projects.length > 1;

  const counterLabel = `Project ${slide + 1} of ${projects.length}: ${projects[slide]?.name ?? ""}`;

  return (
    <section id="work" className="border-t border-ink/15 bg-cream py-20 sm:py-28">
      <div className="mx-auto max-w-[1600px] px-5 sm:px-8">
        <h2 className="display section-title heading-flush break-words text-ink">Featured Work</h2>
      </div>

      <div
        id="featured-work-track"
        ref={trackRef}
        onScroll={onTrackScroll}
        onKeyDown={onTrackKeyDown}
        onTouchStart={onTrackTouchStart}
        onTouchEnd={onTrackTouchEnd}

        role="group"
        aria-roledescription="carousel"
        aria-label="Featured work projects"
        data-reduced-motion={reducedMotion ? "true" : "false"}
        style={reducedMotion ? { scrollBehavior: "auto" } : undefined}
        className="no-scrollbar mx-auto mt-12 flex max-w-[1600px] snap-x snap-mandatory scroll-pl-5 gap-6 overflow-x-auto px-5 pb-6 sm:scroll-pl-8 sm:px-8"
      >
        {projects.map((project, index) => (
          <article
            key={project.slug}
            role="group"
            aria-roledescription="slide"
            aria-label={`${index + 1} of ${projects.length}: ${project.name}`}
            data-slide-index={index}
            data-current={slide === index ? "true" : "false"}
            className="group relative w-[calc(100vw-2.5rem)] max-w-[720px] shrink-0 snap-start sm:w-[58vw] lg:w-[44vw]"
          >
            {/* Stretched hit area: keeps the whole card clickable while the
                copy below stays real heading/paragraph markup. */}
            <button
              type="button"
              ref={(node) => {
                cardRefs.current[index] = node;
              }}
              onClick={() => openAt(index)}
              onMouseEnter={() => warm(project.image)}
              onFocus={() => warm(project.image)}
              onTouchStart={() => warm(project.image)}
              aria-haspopup="dialog"
              aria-expanded={openIndex === index}
              aria-label={`View ${project.name} — ${project.category} project`}
              className="absolute inset-0 z-10 cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-4 focus-visible:ring-offset-cream"
            />
            <div className="block w-full text-left">
              <span className="block overflow-hidden">
                <WorkImage
                  src={project.image}
                  alt={project.alt}
                  slug={project.slug}
                  variant="thumbnail"
                  reducedMotion={reducedMotion}
                  className={`aspect-[3/2] w-full ${
                    reducedMotion
                      ? ""
                      : "transition-transform duration-500 ease-out group-hover:scale-[1.03]"
                  }`}
                />
              </span>
              <p className="label-caps mt-5 text-accent">{project.category}</p>
              <h3
                className="display mt-2 text-ink"
                style={{ fontSize: "clamp(1.75rem, 3.4vw, 3rem)" }}
              >
                {project.name}
              </h3>
              <p className="mt-3 max-w-xl text-sm leading-relaxed text-ink/80">{project.note}</p>
            </div>
          </article>
        ))}
      </div>

      {/* Mobile: one project per view, stepped with arrows instead of a scrollbar. */}
      {steppable && (
        <div
          className="mx-auto flex max-w-[1600px] items-center gap-3 px-5 sm:hidden"
          role="group"
          aria-label="Featured work carousel navigation"
        >
          <button
            type="button"
            data-testid="carousel-prev"
            onClick={() => scrollToCard(slide - 1)}
            aria-label={`Previous project: ${
              projects[(slide - 1 + projects.length) % projects.length]?.name ?? ""
            }`}
            aria-controls="featured-work-track"
            className="flex h-11 w-11 shrink-0 cursor-pointer items-center justify-center border border-ink/20 text-ink transition-colors hover:bg-ink hover:text-cream"
          >
            <ArrowLeft className="h-5 w-5" aria-hidden="true" />
          </button>
          <button
            type="button"
            data-testid="carousel-next"
            onClick={() => scrollToCard(slide + 1)}
            aria-label={`Next project: ${projects[(slide + 1) % projects.length]?.name ?? ""}`}
            aria-controls="featured-work-track"
            className="flex h-11 w-11 shrink-0 cursor-pointer items-center justify-center border border-ink/20 text-ink transition-colors hover:bg-ink hover:text-cream"
          >
            <ArrowRight className="h-5 w-5" aria-hidden="true" />
          </button>
          <span
            className="label-caps ml-2 text-ink/70"
            data-testid="carousel-counter"
            aria-hidden="true"
          >
            {String(slide + 1).padStart(2, "0")} / {String(projects.length).padStart(2, "0")}
          </span>
          <span className="sr-only" role="status" aria-live="polite" aria-atomic="true">
            {counterLabel}
          </span>
        </div>
      )}

      <DialogPrimitive.Root
        open={isOpen}
        onOpenChange={(next) => {
          if (!next) close();
        }}
      >
        <DialogPrimitive.Portal>
          <DialogPrimitive.Overlay
            aria-hidden="true"
            data-reduced-motion={reducedMotion ? "true" : "false"}
            className={`fixed inset-0 z-50 bg-ink/90 ${motionClasses}`}
          />
          <DialogPrimitive.Content
            ref={contentRef}
            aria-label={active ? `${active.name} project details` : "Project details"}
            onCloseAutoFocus={(event) => {
              event.preventDefault();
              const card = cardRefs.current[openIndexRef.current];
              card?.focus();
              card?.scrollIntoView({ block: "nearest", inline: "nearest" });
            }}
            onTouchStart={(event) => {
              const touch = event.touches[0];
              touchStart.current = touch ? { x: touch.clientX, y: touch.clientY } : null;
            }}
            onTouchEnd={(event) => {
              const start = touchStart.current;
              touchStart.current = null;
              if (!start) return;
              const touch = event.changedTouches[0];
              if (!touch) return;
              const dx = touch.clientX - start.x;
              const dy = touch.clientY - start.y;
              if (Math.abs(dx) < SWIPE_THRESHOLD || Math.abs(dx) < Math.abs(dy) * 1.5) return;
              step(dx < 0 ? 1 : -1);
            }}
            data-reduced-motion={reducedMotion ? "true" : "false"}
            className={`fixed inset-0 z-50 overflow-y-auto bg-cream focus:outline-none ${motionClasses}`}
          >
            {active ? (
              <div className="mx-auto flex min-h-full max-w-[1400px] flex-col px-5 py-6 sm:px-8 sm:py-8">
                <div className="flex items-center justify-between">
                  {steppable ? (
                    <div
                      className="flex items-center gap-2"
                      role="group"
                      aria-label="Project navigation"
                    >
                      <button
                        type="button"
                        onClick={() => step(-1)}
                        aria-label={`Previous project: ${prevProject?.name ?? ""}`}
                        aria-controls="work-lightbox-detail"
                        className="flex h-11 w-11 cursor-pointer items-center justify-center border border-ink/20 text-ink transition-colors hover:bg-ink hover:text-cream"
                      >
                        <ArrowLeft className="h-5 w-5" aria-hidden="true" />
                      </button>
                      <button
                        type="button"
                        onClick={() => step(1)}
                        aria-label={`Next project: ${nextProject?.name ?? ""}`}
                        aria-controls="work-lightbox-detail"
                        className="flex h-11 w-11 cursor-pointer items-center justify-center border border-ink/20 text-ink transition-colors hover:bg-ink hover:text-cream"
                      >
                        <ArrowRight className="h-5 w-5" aria-hidden="true" />
                      </button>
                      <span className="label-caps ml-3 text-ink/70">
                        <span className="sr-only">Project </span>
                        {String(openIndexRef.current + 1).padStart(2, "0")} /{" "}
                        {String(projects.length).padStart(2, "0")}
                      </span>
                    </div>
                  ) : (
                    <span />
                  )}
                  <DialogPrimitive.Close
                    aria-label={`Close ${active.name} project details`}
                    className="flex h-11 w-11 cursor-pointer items-center justify-center border border-ink/20 text-ink transition-colors hover:bg-accent hover:border-accent hover:text-cream"
                  >
                    <X className="h-5 w-5" aria-hidden="true" />
                  </DialogPrimitive.Close>
                </div>

                <div id="work-lightbox-detail" aria-live="polite">
                  {/* Ratio is reserved up-front so a deep-linked hard refresh
                      paints the final layout with no shift once the image lands. */}
                  <div
                    data-testid="work-lightbox-frame"
                    className="mt-6 flex aspect-[3/2] max-h-[68vh] w-full items-center justify-center"
                  >
                    <WorkImage
                      key={active.image}
                      src={active.image}
                      alt={active.alt}
                      slug={active.slug}
                      variant="lightbox"
                      reducedMotion={reducedMotion}
                      className="h-full w-full"
                    />
                  </div>

                  {/* Neighbours decode ahead of a swipe / prev-next tap. */}
                  <div aria-hidden="true" className="hidden">
                    {(reducedData ? [] : [prevProject, nextProject])
                      .filter((p) => p && p.slug !== active.slug)
                      .map((p) => (
                        <img
                          key={`preload-${p!.slug}`}
                          src={p!.image}
                          alt=""
                          loading="eager"
                          decoding="async"
                          fetchPriority="low"
                        />
                      ))}
                  </div>

                  <div className="mt-8 pb-4">
                    <p className="label-caps text-accent">{active.category}</p>
                    <DialogPrimitive.Title
                      className="display mt-2 text-ink"
                      style={{ fontSize: "clamp(2rem, 5vw, 4.25rem)" }}
                    >
                      {active.name}
                    </DialogPrimitive.Title>
                    <DialogPrimitive.Description className="mt-4 max-w-2xl text-base leading-relaxed text-ink/70">
                      {active.note}
                    </DialogPrimitive.Description>
                  </div>
                </div>
                <p className="sr-only">
                  Swipe left or right, or use the arrow keys, to move between projects. Press Escape
                  to close.
                </p>
              </div>
            ) : null}
          </DialogPrimitive.Content>
        </DialogPrimitive.Portal>
      </DialogPrimitive.Root>
    </section>
  );
}

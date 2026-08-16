/**
 * Lightweight performance log for the Featured Work section.
 *
 * Every entry is kept on `window.__featuredWorkPerf` so a run can be inspected
 * from the console or scraped by a Playwright check. Enable console output with
 * `?perf=1` in the URL or `localStorage.setItem("fw:perf", "1")`.
 */

export type PerfEvent = {
  /** e.g. "thumbnail:render", "lightbox:open", "image:decode" */
  name: string;
  /** Project slug the event belongs to, when applicable. */
  slug?: string | undefined;
  /** High-resolution timestamp (ms since navigation start). */
  at: number;
  /** Duration in ms for events that measure a span. */
  duration?: number | undefined;
  /** Whether the asset came from the prefetch cache. */
  prefetched?: boolean | undefined;
  /** Extra context (network mode, retry count, …). */
  detail?: Record<string, unknown> | undefined;
};

type PerfWindow = Window & {
  __featuredWorkPerf?: PerfEvent[];
  __featuredWorkPerfVerbose?: boolean;
};

export function now(): number {
  if (typeof performance !== "undefined") return performance.now();
  return Date.now();
}

function verbose(win: PerfWindow): boolean {
  if (win.__featuredWorkPerfVerbose !== undefined) return win.__featuredWorkPerfVerbose;
  let on = false;
  try {
    on =
      new URLSearchParams(win.location.search).get("perf") === "1" ||
      win.localStorage?.getItem("fw:perf") === "1";
  } catch {
    on = false;
  }
  win.__featuredWorkPerfVerbose = on;
  return on;
}

/** Record a Featured Work performance event. No-ops during SSR. */
export function logPerf(event: Omit<PerfEvent, "at"> & { at?: number | undefined }): PerfEvent | null {
  if (typeof window === "undefined") return null;
  const win = window as PerfWindow;
  const entry: PerfEvent = { ...event, at: event.at ?? now() };
  const log = (win.__featuredWorkPerf ??= []);
  log.push(entry);

  if (typeof performance !== "undefined" && typeof performance.mark === "function") {
    try {
      performance.mark(`fw:${entry.name}${entry.slug ? `:${entry.slug}` : ""}`);
    } catch {
      /* mark budget exhausted — the in-memory log is the source of truth */
    }
  }

  if (verbose(win)) {
    const ms = entry.duration !== undefined ? ` ${entry.duration.toFixed(1)}ms` : "";
    const tag = entry.prefetched === undefined ? "" : entry.prefetched ? " [prefetched]" : " [cold]";
    // eslint-disable-next-line no-console
    console.debug(
      `[featured-work] ${entry.name}${entry.slug ? ` ${entry.slug}` : ""}${ms}${tag}`,
      entry.detail ?? "",
    );
  }

  return entry;
}

/** Start a span; call the returned fn to log it with its duration. */
export function startPerf(name: string, slug?: string) {
  const started = now();
  return (extra?: Partial<PerfEvent>) =>
    logPerf({ name, slug, duration: now() - started, ...extra });
}

/** All events recorded so far (newest last). */
export function getPerfLog(): PerfEvent[] {
  if (typeof window === "undefined") return [];
  return [...((window as PerfWindow).__featuredWorkPerf ?? [])];
}

export function clearPerfLog(): void {
  if (typeof window === "undefined") return;
  (window as PerfWindow).__featuredWorkPerf = [];
}

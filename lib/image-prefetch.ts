import { logPerf, now } from "@/lib/perf-log";

const cache = new Map<string, Promise<void>>();
/** Sources that have fully loaded + decoded via the prefetcher. */
const ready = new Set<string>();

type NetworkInfo = {
  saveData?: boolean;
  effectiveType?: string;
  downlink?: number;
  addEventListener?: (type: "change", cb: () => void) => void;
  removeEventListener?: (type: "change", cb: () => void) => void;
};

export type NetworkMode = {
  /** True when we must avoid speculative image fetching. */
  reducedData: boolean;
  reason: "save-data" | "slow-connection" | "offline" | "ok" | "unknown";
  effectiveType?: string | undefined;
  downlink?: number | undefined;
};

const SLOW_TYPES = new Set(["slow-2g", "2g"]);

function connection(): NetworkInfo | undefined {
  if (typeof navigator === "undefined") return undefined;
  const nav = navigator as Navigator & {
    connection?: NetworkInfo;
    mozConnection?: NetworkInfo;
    webkitConnection?: NetworkInfo;
  };
  return nav.connection ?? nav.mozConnection ?? nav.webkitConnection;
}

/** Current data-usage posture. Safe to call during SSR (returns "unknown"). */
export function getNetworkMode(): NetworkMode {
  if (typeof navigator === "undefined") return { reducedData: true, reason: "unknown" };
  if (navigator.onLine === false) return { reducedData: true, reason: "offline" };

  const conn = connection();
  if (!conn) return { reducedData: false, reason: "unknown" };
  if (conn.saveData) {
    return { reducedData: true, reason: "save-data", effectiveType: conn.effectiveType };
  }
  const slow =
    (conn.effectiveType && SLOW_TYPES.has(conn.effectiveType)) ||
    (typeof conn.downlink === "number" && conn.downlink > 0 && conn.downlink < 0.5);
  return {
    reducedData: Boolean(slow),
    reason: slow ? "slow-connection" : "ok",
    effectiveType: conn.effectiveType,
    downlink: conn.downlink,
  };
}

/** Subscribe to connection/online changes. Returns an unsubscribe fn. */
export function subscribeToNetwork(onChange: () => void): () => void {
  if (typeof window === "undefined") return () => {};
  const conn = connection();
  conn?.addEventListener?.("change", onChange);
  window.addEventListener("online", onChange);
  window.addEventListener("offline", onChange);
  return () => {
    conn?.removeEventListener?.("change", onChange);
    window.removeEventListener("online", onChange);
    window.removeEventListener("offline", onChange);
  };
}

/** True when the user is on a metered, offline or very slow connection. */
export function shouldSkipPrefetch(): boolean {
  return getNetworkMode().reducedData;
}

/** Has this source already been warmed (and therefore decodes instantly)? */
export function isPrefetched(src: string): boolean {
  return ready.has(src);
}

/**
 * Warm the browser cache for a single image. Safe to call repeatedly.
 * Pass `{ force: true }` to bypass the reduced-data guard (user-intent loads).
 */
export function prefetchImage(src: string, options: { force?: boolean } = {}): Promise<void> {
  if (typeof window === "undefined" || !src) return Promise.resolve();
  if (!options.force && shouldSkipPrefetch()) return Promise.resolve();
  const existing = cache.get(src);
  if (existing) return existing;

  const started = now();
  const promise = new Promise<void>((resolve) => {
    const image = new Image();
    image.decoding = "async";
    (image as HTMLImageElement & { fetchPriority?: string }).fetchPriority = "low";
    const done = () => {
      ready.add(src);
      logPerf({ name: "prefetch:ready", duration: now() - started, detail: { src } });
      resolve();
    };
    image.onload = () => {
      if (typeof image.decode === "function") {
        image.decode().then(done, done);
      } else {
        done();
      }
    };
    image.onerror = () => {
      cache.delete(src);
      logPerf({ name: "prefetch:error", duration: now() - started, detail: { src } });
      resolve();
    };
    image.src = src;
  });

  cache.set(src, promise);
  return promise;
}

/** Forget a source so the next attempt refetches it (used by retry). */
export function invalidatePrefetch(src: string): void {
  cache.delete(src);
  ready.delete(src);
}

/** Prefetch a list of images when the browser is idle. Returns a cancel fn. */
export function prefetchImagesWhenIdle(sources: string[]): () => void {
  if (typeof window === "undefined") return () => {};
  const mode = getNetworkMode();
  if (mode.reducedData) {
    logPerf({ name: "prefetch:skipped", detail: { reason: mode.reason, count: sources.length } });
    return () => {};
  }
  const idle = (
    window as Window & {
      requestIdleCallback?: (cb: () => void, opts?: { timeout: number }) => number;
      cancelIdleCallback?: (id: number) => void;
    }
  ).requestIdleCallback;

  if (idle) {
    const id = idle(() => sources.forEach((src) => void prefetchImage(src)), { timeout: 2000 });
    return () =>
      (window as Window & { cancelIdleCallback?: (id: number) => void }).cancelIdleCallback?.(id);
  }

  const timer = window.setTimeout(() => sources.forEach((src) => void prefetchImage(src)), 300);
  return () => window.clearTimeout(timer);
}

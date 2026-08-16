"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ImageOff, RotateCw } from "lucide-react";

import { invalidatePrefetch, isPrefetched } from "@/lib/image-prefetch";
import { logPerf, now } from "@/lib/perf-log";

type Props = {
  src: string;
  alt: string;
  slug: string;
  /** "thumbnail" (card) or "lightbox" — used for perf event names + sizing. */
  variant: "thumbnail" | "lightbox";
  className?: string;
  reducedMotion?: boolean;
};

/**
 * Featured Work image with a loading skeleton, fade-in, decode timing and an
 * error fallback that lets the visitor retry a failed load.
 */
export function WorkImage({ src, alt, slug, variant, className = "", reducedMotion }: Props) {
  const [status, setStatus] = useState<"loading" | "loaded" | "error">("loading");
  const [attempt, setAttempt] = useState(0);
  const startedAt = useRef(now());
  const imgRef = useRef<HTMLImageElement | null>(null);
  const isLightbox = variant === "lightbox";

  // A new source (or retry) restarts the cycle.
  useEffect(() => {
    startedAt.current = now();
    setStatus("loading");
  }, [src, attempt]);

  // A server-rendered / cached image can settle before React attaches its
  // handlers, so reconcile from the DOM once after mount.
  useEffect(() => {
    const node = imgRef.current;
    if (!node?.complete) return;
    setStatus(node.naturalWidth > 0 ? "loaded" : "error");
  }, [src, attempt]);

  const handleLoad = useCallback(() => {
    setStatus("loaded");
    logPerf({
      name: `${variant}:decode`,
      slug,
      duration: now() - startedAt.current,
      prefetched: isPrefetched(src),
      detail: { attempt },
    });
  }, [attempt, slug, src, variant]);

  const handleError = useCallback(() => {
    setStatus("error");
    logPerf({ name: `${variant}:error`, slug, detail: { src, attempt } });
  }, [attempt, slug, src, variant]);

  const retry = useCallback(() => {
    invalidatePrefetch(src);
    logPerf({ name: `${variant}:retry`, slug, detail: { attempt: attempt + 1 } });
    setAttempt((a) => a + 1);
  }, [attempt, slug, src, variant]);

  if (status === "error") {
    return (
      <div
        data-testid={`work-image-error-${variant}`}
        role="group"
        aria-label={`${alt} failed to load`}
        className={`flex flex-col items-center justify-center gap-4 border border-ink/15 bg-ink/5 p-6 text-center ${className}`}
      >
        <ImageOff className="h-7 w-7 text-ink/40" aria-hidden="true" />
        <p className="max-w-xs text-sm leading-relaxed text-ink/60">
          This image couldn’t be loaded.
        </p>
        <button
          type="button"
          onClick={(event) => {
            event.stopPropagation();
            retry();
          }}
          className="label-caps flex cursor-pointer items-center gap-2 border border-ink/25 px-4 py-2 text-ink transition-colors hover:border-accent hover:bg-accent hover:text-cream"
        >
          <RotateCw className="h-4 w-4" aria-hidden="true" />
          Retry
        </button>
      </div>
    );
  }

  return (
    <span className={`relative block overflow-hidden ${className}`}>
      {status === "loading" ? (
        <span
          aria-hidden="true"
          data-testid={`work-image-skeleton-${variant}`}
          className={`absolute inset-0 block bg-ink/10 ${reducedMotion ? "" : "animate-pulse"}`}
        />
      ) : null}
      <img
        // Force a fresh element per retry so the browser re-requests the file.
        key={`${src}#${attempt}`}
        ref={imgRef}
        src={src}
        alt={alt}
        width={1200}
        height={800}
        loading={isLightbox ? "eager" : "lazy"}
        decoding="async"
        fetchPriority={isLightbox ? "high" : "auto"}
        onLoad={handleLoad}
        onError={handleError}
        data-loaded={status === "loaded" ? "true" : "false"}
        className={`h-full w-full ${isLightbox ? "object-contain" : "aspect-[3/2] object-cover"} ${
          reducedMotion ? "" : "transition-opacity duration-500 ease-out"
        } ${status === "loaded" ? "opacity-100" : "opacity-0"}`}
      />
    </span>
  );
}

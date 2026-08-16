/**
 * Route metadata helper.
 *
 * `routeMetadata()` feeds a route's `export const metadata`. The pieces Next
 * would rewrite are emitted by hand instead — see `routeSeoTags()`: Next
 * resolves `openGraph.url` and `alternates.canonical` against `metadataBase`,
 * so a relative "/" would render as an absolute origin-prefixed URL. The shared
 * expectations in tests/head-metadata.expected.json want the literal "/", so
 * those two tags stay hand-written.
 *
 *   export const metadata = routeMetadata({ title, description, path: "/" });
 */

import type { Metadata } from "next";

export type RouteMetadata = {
  title: string;
  description: string;
  /** Route path, e.g. "/" or "/about". Used for canonical + og:url. */
  path: string;
  /** Absolute https URL of a meaningful hero/cover image. Leaf routes only. */
  image?: string;
  type?: "website" | "article";
  robots?: string;
  siteName?: string;
};

export function routeMetadata(meta: RouteMetadata): Metadata {
  const { title, description, image, type = "website", robots, siteName } = meta;

  return {
    title,
    description,
    authors: [{ name: "Lovable" }],
    openGraph: {
      title,
      description,
      type,
      ...(siteName ? { siteName } : {}),
      ...(image ? { images: [image] } : {}),
    },
    twitter: {
      card: image ? "summary_large_image" : "summary",
      site: "@Lovable",
      title,
      description,
      ...(image ? { images: [image] } : {}),
    },
    ...(robots ? { robots } : {}),
  };
}

/** The tags Next would otherwise absolutise. Render inside the route's JSX. */
export function routeSeoTags(meta: Pick<RouteMetadata, "path">) {
  return { ogUrl: meta.path, canonical: meta.path };
}

/**
 * Route metadata helper.
 *
 * Feeds a route's `export const metadata`. `metadataBase` is set in the root
 * layout, so the relative `path` given here is resolved to an absolute URL for
 * `canonical`, `og:url` and image tags — which is what crawlers and social
 * scrapers require. Anything relative gets treated as a same-origin path by
 * some scrapers and dropped entirely by others.
 *
 *   export const metadata = routeMetadata({ title, description, path: "/" });
 */

import type { Metadata } from "next";

import { siteName } from "@/lib/site";

export type RouteMetadata = {
  title: string;
  description: string;
  /** Route path, e.g. "/" or "/about". Resolved against metadataBase. */
  path: string;
  /** Cover image path/URL. Defaults to the site-wide Open Graph card. */
  image?: string;
  /** Alt text for the cover image — screen readers on X/LinkedIn read this. */
  imageAlt?: string;
  type?: "website" | "article";
  robots?: Metadata["robots"];
};

export const defaultOgImage = "/og.jpg";
export const defaultOgImageAlt =
  "Brand Ledger — we build brands that behave like businesses. Brand and digital studio, Omaha, Nebraska.";

export function routeMetadata(meta: RouteMetadata): Metadata {
  const {
    title,
    description,
    path,
    image = defaultOgImage,
    imageAlt = defaultOgImageAlt,
    type = "website",
    robots,
  } = meta;

  const images = [{ url: image, width: 1200, height: 630, alt: imageAlt }];

  return {
    title,
    description,
    alternates: { canonical: path },
    openGraph: {
      title,
      description,
      type,
      url: path,
      siteName,
      locale: "en_US",
      images,
    },
    twitter: {
      card: "summary_large_image",
      title,
      description,
      images,
    },
    ...(robots ? { robots } : {}),
  };
}

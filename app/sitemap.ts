import type { MetadataRoute } from "next";

import { contentUpdated, siteUrl } from "@/lib/site";

export default function sitemap(): MetadataRoute.Sitemap {
  // One indexable document. The `?work=` deep links render the same page with a
  // lightbox over it, so they are deliberately left out: submitting them would
  // offer near-duplicate URLs that all canonicalise back to "/".
  // No trailing slash, so this is byte-identical to the canonical Next derives
  // from metadataBase — a sitemap that disagrees with the canonical tag just
  // gives crawlers two candidate URLs to reconcile.
  return [
    {
      url: siteUrl,
      lastModified: contentUpdated,
      changeFrequency: "monthly",
      priority: 1,
    },
  ];
}

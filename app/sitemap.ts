import { join } from "node:path";

import type { MetadataRoute } from "next";

import { discoverStaticRoutes } from "@/lib/routes";
import { contentUpdated, siteUrl } from "@/lib/site";

/**
 * /sitemap.xml, generated from the routes that actually exist.
 *
 * Every `page` file under app/ is listed automatically, so adding a page puts
 * it in the sitemap without anyone remembering to. The previous version was a
 * single hardcoded entry, which was correct for a one-page site and silently
 * wrong the moment it stopped being one.
 *
 * The `?work=` deep links stay out deliberately. They render the same document
 * with a lightbox over it and canonicalise back to "/", so submitting them
 * would hand crawlers a set of near-duplicate URLs to reconcile against a
 * canonical that disagrees with all of them.
 *
 * URLs carry no trailing slash, matching the canonical Next derives from
 * metadataBase byte for byte. A sitemap that disagrees with the canonical tag
 * is worse than no sitemap: it nominates one URL while the page nominates
 * another.
 */

/**
 * Per-route overrides. Anything not listed takes the defaults below, so a new
 * page is published on sensible values rather than waiting on a config edit.
 * Add a route here only when it genuinely differs.
 */
const ROUTE_META: Record<string, Partial<MetadataRoute.Sitemap[number]>> = {
  "/": { changeFrequency: "monthly", priority: 1 },
};

const DEFAULT_META = { changeFrequency: "monthly", priority: 0.7 } as const;

/**
 * Routes to publish that discovery cannot see — dynamic segments, whose
 * addresses live in data rather than on disk. Empty today: the work items are
 * query-string deep links onto "/", not routes of their own. When a project or
 * post gets a real URL, map its list to paths here.
 *
 *   ...projects.map((project) => `/work/${project.slug}`)
 */
const DYNAMIC_ROUTES: string[] = [];

/** Discovered routes that should exist but not be indexed. */
const EXCLUDED = new Set<string>([]);

export default function sitemap(): MetadataRoute.Sitemap {
  const discovered = discoverStaticRoutes(join(process.cwd(), "app"));

  // Fall back rather than emit an empty sitemap: if discovery ever comes back
  // with nothing (an unexpected build layout, a cwd that is not the project
  // root), publishing "/" is right, and publishing nothing tells Search Console
  // the site has no pages.
  const paths = discovered.length > 0 ? discovered : ["/"];

  return [...new Set([...paths, ...DYNAMIC_ROUTES])]
    .filter((path) => !EXCLUDED.has(path))
    .sort()
    .map((path) => ({
      // siteUrl has no trailing slash and "/" must not add one back.
      url: path === "/" ? siteUrl : `${siteUrl}${path}`,
      lastModified: contentUpdated,
      ...DEFAULT_META,
      ...ROUTE_META[path],
    }));
}

import { readdirSync, statSync } from "node:fs";
import { join } from "node:path";

/**
 * Route discovery for the sitemap.
 *
 * Walks the app directory and derives a URL path for every `page` file, so a
 * new page appears in /sitemap.xml by existing — nobody has to remember to add
 * it. This runs at build time in the Node runtime, which is where `sitemap.ts`
 * is evaluated; it never ships to the browser.
 *
 * The App Router's folder conventions each mean something different to the URL,
 * and getting them wrong publishes URLs that 404:
 *
 *   about/          -> /about
 *   (marketing)/    -> route group: organisational only, contributes no segment
 *   _internal/      -> private folder: not routable at all
 *   @modal/         -> parallel route slot: rendered into a layout, not a URL
 *   [slug]/         -> dynamic: the path is a pattern, not an address
 *   (.)photo/       -> intercepting route: an alternate render of another URL
 *
 * Dynamic segments are the one case discovery cannot resolve on its own, since
 * the addresses live in data rather than on disk. Pass them in via
 * `additionalRoutes` from whatever list generates them.
 */

const PAGE_FILES = ["page.tsx", "page.ts", "page.jsx", "page.js", "page.mdx"];

/** Folder is organisational, not addressable — traverse it, add no segment. */
function isRouteGroup(name: string): boolean {
  return name.startsWith("(") && name.endsWith(")");
}

/** Folder produces no URL of its own and must not be walked for one. */
function isNonRoutable(name: string): boolean {
  return (
    name.startsWith("_") || // private folder
    name.startsWith("@") || // parallel route slot
    name.startsWith("[") || // dynamic segment — addresses come from data
    name.startsWith("(.") || // intercepting route, incl. (..) and (...)
    name === "api" || // route handlers, not documents
    name === "node_modules"
  );
}

function hasPage(dir: string): boolean {
  return PAGE_FILES.some((file) => {
    try {
      return statSync(join(dir, file)).isFile();
    } catch {
      return false;
    }
  });
}

/**
 * Every static route in the app directory, as absolute paths beginning "/".
 * Sorted so the output is stable build to build — an unstable sitemap is a
 * diff that says nothing.
 */
export function discoverStaticRoutes(appDir: string): string[] {
  const routes: string[] = [];

  const walk = (dir: string, segments: string[]) => {
    if (hasPage(dir)) routes.push("/" + segments.join("/"));

    let entries: string[];
    try {
      entries = readdirSync(dir);
    } catch {
      return; // unreadable directory is not worth failing a build over
    }

    for (const entry of entries) {
      let isDir = false;
      try {
        isDir = statSync(join(dir, entry)).isDirectory();
      } catch {
        continue;
      }
      if (!isDir || isNonRoutable(entry)) continue;
      walk(join(dir, entry), isRouteGroup(entry) ? segments : [...segments, entry]);
    }
  };

  walk(appDir, []);
  // "/" comes out as "" from the join above; normalise it, then dedupe, because
  // two route groups can legitimately resolve to the same path.
  return [...new Set(routes.map((route) => (route === "/" ? "/" : route.replace(/\/+$/, ""))))]
    .map((route) => (route === "" ? "/" : route))
    .sort();
}

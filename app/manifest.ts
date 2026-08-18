import type { MetadataRoute } from "next";

import { siteDescription, siteName } from "@/lib/site";

/**
 * Web app manifest, served at /manifest.webmanifest.
 *
 * This exists for the icon sizes the <link> tags do not cover: Android's
 * install prompt and home-screen shortcut read 192 and 512 from here, and
 * without them Chrome falls back to a screenshot of the page. `maskable`
 * is declared alongside `any` because the mark is a full-bleed square with
 * the wordmark well inside the safe area, so it survives being clipped to
 * a circle or squircle without a transparent margin.
 *
 * theme_color matches the fixed ink masthead (and the themeColor in the root
 * layout's viewport export), so the Android status bar does not sit in a
 * default light strip above a black header.
 */
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: `${siteName} — Content Strategy, Web Design & UX in Omaha`,
    short_name: siteName,
    description: siteDescription,
    start_url: "/",
    display: "standalone",
    background_color: "#0d0d0d",
    theme_color: "#0d0d0d",
    icons: [
      { src: "/icon-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
      { src: "/icon-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
      { src: "/icon-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
  };
}

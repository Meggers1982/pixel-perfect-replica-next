/**
 * Single source of truth for the things SEO output, structured data and the
 * footer all need to agree on.
 *
 * `NEXT_PUBLIC_SITE_URL` overrides the origin — set it per environment (preview
 * deploys, staging) so canonical, og:url and the sitemap always point at the
 * host actually being served. The default is the production domain implied by
 * the studio's contact address.
 */

export const siteUrl = (process.env.NEXT_PUBLIC_SITE_URL ?? "https://thebrandledger.com").replace(
  /\/+$/,
  "",
);

export const siteName = "Brand Ledger";

export const siteDescription =
  "Omaha brand and digital studio building identity, positioning and product for founder-led consumer and healthcare companies.";

export const contact = {
  email: "hello@thebrandledger.com",
  /** E.164, for tel: links and structured data. */
  phone: "+14029572262",
  phoneDisplay: "(402) 957-2262",
  locality: "Omaha",
  region: "NE",
  country: "US",
} as const;

/**
 * Formspree endpoint the contact form posts to. Public by design — it is a
 * write-only submission URL, not a credential — so it ships in the client
 * bundle. Override per environment to keep test traffic out of the real inbox.
 */
export const formEndpoint =
  process.env.NEXT_PUBLIC_FORMSPREE_ENDPOINT ?? "https://formspree.io/f/xdenwnlp";

export const founded = "2014";

export const founders = ["Dana Whitcomb", "Elias Roche"] as const;

/** Absolute URL for a site-relative path. */
export function absoluteUrl(path: string): string {
  return `${siteUrl}${path.startsWith("/") ? path : `/${path}`}`;
}

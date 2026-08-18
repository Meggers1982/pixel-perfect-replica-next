import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";

import { Providers } from "@/app/providers";
import { defaultOgImage, defaultOgImageAlt } from "@/lib/seo";
import { siteDescription, siteName, siteUrl } from "@/lib/site";
import "./globals.css";

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  // Matches the fixed ink header, so mobile browser chrome does not sit in a
  // default light bar above a black masthead.
  themeColor: "#0d0d0d",
};

// Shell-level defaults. The index route overrides title/description/og/twitter;
// what survives here is what every route shares — including the 404, which is
// why these are real values rather than placeholders.
export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: {
    default: `${siteName} — Brand & Digital Studio in Omaha`,
    template: `%s | ${siteName}`,
  },
  description: siteDescription,
  applicationName: siteName,
  authors: [{ name: siteName, url: siteUrl }],
  creator: siteName,
  publisher: siteName,
  openGraph: {
    title: `${siteName} — Brand & Digital Studio in Omaha`,
    description: siteDescription,
    type: "website",
    url: "/",
    siteName,
    locale: "en_US",
    images: [{ url: defaultOgImage, width: 1200, height: 630, alt: defaultOgImageAlt }],
  },
  twitter: {
    card: "summary_large_image",
    title: `${siteName} — Brand & Digital Studio in Omaha`,
    description: siteDescription,
    images: [{ url: defaultOgImage, alt: defaultOgImageAlt }],
  },
  robots: {
    index: true,
    follow: true,
    googleBot: { index: true, follow: true, "max-image-preview": "large", "max-snippet": -1 },
  },
  icons: {
    icon: [{ url: "/favicon.ico", type: "image/x-icon" }],
    apple: [{ url: "/apple-icon.png", sizes: "180x180", type: "image/png" }],
  },
  formatDetection: { telephone: false },
};

// Anton/Barlow are self-hosted, so nothing discovers them until the stylesheet
// is parsed — preload them alongside the document to shorten the window where
// text renders in the fallback face. 700 is here because the About section sets
// several names in <strong>, which would otherwise swap a beat after the rest
// of the paragraph has settled.
const PRELOADED_FONTS = [
  "/fonts/anton-400.woff2",
  "/fonts/barlow-400.woff2",
  "/fonts/barlow-500.woff2",
  "/fonts/barlow-700.woff2",
];

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        {PRELOADED_FONTS.map((href) => (
          <link
            key={href}
            rel="preload"
            as="font"
            type="font/woff2"
            href={href}
            crossOrigin="anonymous"
          />
        ))}
        {/* First tab stop on the page: lets keyboard and switch users jump the
            fixed masthead instead of tabbing the whole nav on every visit. */}
        <a
          href="#top"
          className="label-caps sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:bg-cream focus:px-5 focus:py-3 focus:text-ink focus:outline-none focus:ring-2 focus:ring-accent"
        >
          Skip to content
        </a>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}

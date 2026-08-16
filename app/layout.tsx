import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";

import { Providers } from "@/app/providers";
import "./globals.css";

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
};

// Shell-level defaults. The index route overrides title/description/og/twitter;
// what survives here is what every route shares.
export const metadata: Metadata = {
  title: "Lovable App",
  description: "Lovable Generated Project",
  authors: [{ name: "Lovable" }],
  openGraph: {
    title: "Lovable App",
    description: "Lovable Generated Project",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    site: "@Lovable",
  },
  icons: [{ rel: "icon", url: "/favicon.ico", type: "image/x-icon" }],
};

// Anton/Barlow are self-hosted with font-display: block, so the first paint of
// any text waits on these bytes — preload them alongside the document.
const PRELOADED_FONTS = ["/fonts/anton-400.woff2", "/fonts/barlow-400.woff2", "/fonts/barlow-500.woff2"];

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        {PRELOADED_FONTS.map((href) => (
          <link key={href} rel="preload" as="font" type="font/woff2" href={href} crossOrigin="anonymous" />
        ))}
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}

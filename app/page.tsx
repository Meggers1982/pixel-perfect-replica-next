import { About } from "@/components/About";
import { Capabilities } from "@/components/Capabilities";
import { CookieBar } from "@/components/CookieBar";
import { FeaturedWork } from "@/components/FeaturedWork";
import { Hero } from "@/components/Hero";
import { ServicePillars } from "@/components/ServicePillars";
import { SiteFooter } from "@/components/SiteFooter";
import { SiteNav } from "@/components/SiteNav";
import { Toaster } from "@/components/ui/sonner";
import { routeMetadata, routeSeoTags } from "@/lib/seo";

const title = "Brand Ledger — Brand & Digital for Founder-Led Companies";
const description =
  "Omaha brand and digital studio building identity, positioning and product for founder-led consumer and healthcare companies.";
const path = "/";

export const metadata = routeMetadata({
  title,
  description,
  path,
  type: "website",
  siteName: "Brand Ledger",
});

// `?work=<slug>` deep links must render their lightbox in the server HTML, the
// way the TanStack route's `validateSearch` did. Rendering dynamically also
// lets FeaturedWork read useSearchParams() without a Suspense boundary that
// would keep the section out of the SSR payload.
export const dynamic = "force-dynamic";

const { ogUrl, canonical } = routeSeoTags({ path });

export default function Index() {
  return (
    <div className="bg-cream text-ink">
      <meta property="og:url" content={ogUrl} />
      <link rel="canonical" href={canonical} />
      <SiteNav />
      <main>
        <Hero />
        <ServicePillars />
        <FeaturedWork />
        <Capabilities />
        <About />
      </main>
      <SiteFooter />
      <CookieBar />
      <Toaster />
    </div>
  );
}

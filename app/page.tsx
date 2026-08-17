import { About } from "@/components/About";
import { Capabilities } from "@/components/Capabilities";
import { CookieBar } from "@/components/CookieBar";
import { FeaturedWork } from "@/components/FeaturedWork";
import { Hero } from "@/components/Hero";
import { ServicePillars } from "@/components/ServicePillars";
import { SiteFooter } from "@/components/SiteFooter";
import { SiteNav } from "@/components/SiteNav";
import { Toaster } from "@/components/ui/sonner";
import { routeMetadata } from "@/lib/seo";
import { buildStructuredData } from "@/lib/structured-data";

const title = "Brand Ledger — Brand & Digital for Founder-Led Companies";
const description =
  "Omaha brand and digital studio building identity, positioning and product for founder-led consumer and healthcare companies.";

export const metadata = routeMetadata({
  title,
  description,
  path: "/",
  type: "website",
});

// `?work=<slug>` deep links must render their lightbox in the server HTML, the
// way the TanStack route's `validateSearch` did. Rendering dynamically also
// lets FeaturedWork read useSearchParams() without a Suspense boundary that
// would keep the section out of the SSR payload.
export const dynamic = "force-dynamic";

export default function Index() {
  return (
    <div className="bg-cream text-ink">
      <script
        type="application/ld+json"
        // Server-rendered from a typed builder; no user input reaches it.
        dangerouslySetInnerHTML={{ __html: JSON.stringify(buildStructuredData()) }}
      />
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

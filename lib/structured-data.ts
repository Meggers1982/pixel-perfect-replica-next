/**
 * schema.org JSON-LD for the studio.
 *
 * A one-page site gives search engines very little to work with beyond the
 * copy. This spells out the things a brand-and-digital studio actually gets
 * matched on — what it does, where it is, how to reach it, who runs it, and
 * which services it offers — so the entity can be resolved rather than guessed.
 */

import { absoluteUrl, contact, founders, siteDescription, siteName, siteUrl } from "@/lib/site";
import { projects } from "@/lib/projects";

const SERVICES = [
  "Content Strategy",
  "Search Engine Optimization",
  "Generative Engine Optimization",
  "Web Design",
  "UX Design",
] as const;

export function buildStructuredData() {
  const organizationId = `${siteUrl}/#organization`;
  const websiteId = `${siteUrl}/#website`;

  const organization = {
    "@type": "ProfessionalService",
    "@id": organizationId,
    name: siteName,
    url: siteUrl,
    description: siteDescription,
    image: absoluteUrl("/og.jpg"),
    founder: founders.map((name) => ({ "@type": "Person", name })),
    email: contact.email,
    telephone: contact.phone,
    address: {
      "@type": "PostalAddress",
      streetAddress: contact.street,
      addressLocality: contact.locality,
      addressRegion: contact.region,
      postalCode: contact.postalCode,
      addressCountry: contact.country,
    },
    areaServed: { "@type": "Country", name: "United States" },
    knowsAbout: [...SERVICES],
    hasOfferCatalog: {
      "@type": "OfferCatalog",
      name: "Studio services",
      itemListElement: SERVICES.map((service) => ({
        "@type": "Offer",
        itemOffered: { "@type": "Service", name: service, provider: { "@id": organizationId } },
      })),
    },
  };

  const website = {
    "@type": "WebSite",
    "@id": websiteId,
    url: siteUrl,
    name: siteName,
    description: siteDescription,
    publisher: { "@id": organizationId },
    inLanguage: "en-US",
  };

  // The Featured Work carousel is the page's primary content; exposing it as an
  // ItemList lets the individual projects be understood as distinct works
  // rather than one undifferentiated block of body copy.
  const work = {
    "@type": "ItemList",
    "@id": `${siteUrl}/#work`,
    name: "Featured Work",
    itemListOrder: "https://schema.org/ItemListOrderAscending",
    numberOfItems: projects.length,
    itemListElement: projects.map((project, index) => ({
      "@type": "ListItem",
      position: index + 1,
      item: {
        "@type": "CreativeWork",
        name: project.name,
        description: project.note,
        genre: project.category,
        // The live site is the work itself; the portfolio deep link is where it
        // is written about, which is what mainEntityOfPage is for.
        ...(project.url ? { url: project.url } : {}),
        mainEntityOfPage: `${siteUrl}/?work=${encodeURIComponent(project.slug)}#work`,
        image: absoluteUrl(project.image),
        creator: { "@id": organizationId },
      },
    })),
  };

  return { "@context": "https://schema.org", "@graph": [organization, website, work] };
}

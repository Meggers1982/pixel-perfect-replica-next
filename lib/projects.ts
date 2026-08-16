/**
 * Shared Featured Work data — consumed by the carousel, the lightbox and the
 * footer's Work column.
 *
 * Images live in /public/images and are referenced by path rather than imported
 * as modules, so the same `src` string works in server and client components and
 * lands in the markup unrewritten.
 *
 * NOTE: heartland-plein-air-arts-festival-website-project.webp was served from
 * Lovable's asset CDN in the TanStack build and is not in version control.
 * Export it from Lovable into /public/images to restore that card's thumbnail.
 */

export interface Project {
  slug: string;
  category: string;
  name: string;
  image: string;
  alt: string;
  note: string;
}

export const projects: Project[] = [
  {
    slug: "heartland-plein-air-festival",
    category: "Web Development",
    name: "Heartland Plein Air Festival",
    image: "/images/heartland-plein-air-arts-festival-website-project.webp",
    alt: "Heartland Plein Air Festival website hero with painterly landscape and event details",
    note: "Custom event website with schedule, artist gallery, ticketing integration and open-division registration.",
  },
  {
    slug: "hollow-roasters",
    category: "Branding",
    name: "Hollow Roasters",
    image: "/images/work-1.jpg",
    alt: "Specialty coffee packaging with bold minimal labels",
    note: "Identity, packaging system and wholesale collateral for a twelve-city roaster.",
  },
  {
    slug: "field-and-frame",
    category: "Retail",
    name: "Field & Frame",
    image: "/images/work-2.jpg",
    alt: "Modern retail storefront at dusk with bold signage",
    note: "Storefront signage, wayfinding and in-store print for a nine-location optician.",
  },
  {
    slug: "meridian-health",
    category: "Strategy",
    name: "Meridian Health",
    image: "/images/work-3.jpg",
    alt: "Printed annual report spread with bold typography",
    note: "Positioning, messaging hierarchy and annual report design for a payer network.",
  },
];

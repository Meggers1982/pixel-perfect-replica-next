/**
 * Shared Featured Work data — consumed by the carousel, the lightbox and the
 * footer's Work column.
 *
 * Images live in /public/images and are referenced by path rather than imported
 * as modules, so the same `src` string works in server and client components and
 * lands in the markup unrewritten.
 *
 * The Heartland thumbnail is a committed 1200x800 capture of the live project.
 * It used to come from Lovable's asset CDN and was never in version control, so
 * it 404'd after the migration.
 */

export interface Project {
  slug: string;
  category: string;
  name: string;
  image: string;
  alt: string;
  note: string;
  /** Live site, if the work is still published. */
  url?: string;
}

export const projects: Project[] = [
  {
    slug: "heartland-plein-air-festival",
    category: "Content & Web Design",
    name: "Heartland Plein Air Festival",
    image: "/images/heartland-plein-air-arts-festival-website-project.webp",
    alt: "Heartland Plein Air Festival website hero with painterly landscape and event details",
    note: "A week-long festival with twenty-five artists, a public schedule, ticketed events and an open-division competition — each of which had to be findable on its own. We modelled the content so every artist, event and venue is its own page carrying its own schema, and built the wayfinding around the three things visitors actually arrive for: when it is, who is in it, and how to get a ticket.",
    url: "https://heartlandpleinair.org",
  },
];

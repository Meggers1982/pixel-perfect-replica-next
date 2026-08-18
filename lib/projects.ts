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
}

export const projects: Project[] = [
  {
    slug: "heartland-plein-air-festival",
    category: "Content & Web Design",
    name: "Heartland Plein Air Festival",
    image: "/images/heartland-plein-air-arts-festival-website-project.webp",
    alt: "Heartland Plein Air Festival website hero with painterly landscape and event details",
    note: "Content strategy, site architecture and build for a week-long festival — schedule, artist gallery, ticketing and open-division registration, structured so every event and artist page can rank and be cited on its own.",
  },
];

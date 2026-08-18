"use client";

import { useState, type FormEvent } from "react";
import { toast } from "sonner";

import { projects } from "@/lib/projects";
import { addressLines, contact, formEndpoint, siteName } from "@/lib/site";

/** A bare string is a plain fact (no destination); an object is a real link. */
type FooterItem = string | { label: string; href: string };

const columns: { title: string; items: FooterItem[] }[] = [
  {
    title: "Services",
    // These used to point at "#top", which sent visitors back to the masthead
    // and gave crawlers four internal links to nowhere.
    items: ["Content Strategy", "SEO & GEO", "Web Design", "UX Design"].map((label) => ({
      label,
      href: "#services",
    })),
  },
  {
    title: "Work",
    items: projects.map((project) => ({
      label: project.name,
      href: `/?work=${project.slug}#work`,
    })),
  },
  { title: "About", items: [{ label: "The Studio", href: "#about" }] },
];

/* Line icons, sized to the cap height of the text they sit beside. Stroked
   rather than filled so they read at the same weight as the type on the red,
   and aria-hidden because each one duplicates a label that is already there. */
const iconProps = {
  "aria-hidden": true,
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.6,
  strokeLinecap: "round",
  strokeLinejoin: "round",
  className: "mt-0.5 h-[1.15em] w-[1.15em] shrink-0",
} as const;

const MailIcon = () => (
  <svg {...iconProps}>
    <rect x="2" y="4" width="20" height="16" rx="1" />
    <path d="m2 6 10 7 10-7" />
  </svg>
);

const PhoneIcon = () => (
  <svg {...iconProps}>
    <path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.1 4.2 2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1.9.3 1.8.6 2.7a2 2 0 0 1-.4 2.1L8 9.8a16 16 0 0 0 6 6l1.3-1.3a2 2 0 0 1 2.1-.4c.9.3 1.8.5 2.7.6a2 2 0 0 1 1.7 2Z" />
  </svg>
);

const PinIcon = () => (
  <svg {...iconProps}>
    <path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z" />
    <circle cx="12" cy="10" r="3" />
  </svg>
);

type Status = "idle" | "submitting" | "success" | "error";

const SUCCESS_MESSAGE = "Thanks — we'll reply within two business days.";
const GENERIC_ERROR =
  "That didn't send. Try again, or email hello@thebrandledger.com directly.";

/** Formspree replies with `{ errors: [{ message, field }] }` on a rejection. */
async function readFormspreeError(response: Response): Promise<string> {
  try {
    const payload = (await response.json()) as { errors?: { message?: string }[] };
    const message = payload.errors
      ?.map((error) => error.message)
      .filter(Boolean)
      .join(" ");
    return message && message.length > 0 ? message : GENERIC_ERROR;
  } catch {
    return GENERIC_ERROR;
  }
}

export function SiteFooter() {
  const [status, setStatus] = useState<Status>("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    // Captured before the first await: React clears currentTarget once the
    // handler yields.
    const form = event.currentTarget;
    const body = new FormData(form);

    setStatus("submitting");
    setErrorMessage(null);

    try {
      const response = await fetch(formEndpoint, {
        method: "POST",
        body,
        // Without this Formspree answers with a redirect to its own thank-you
        // page instead of JSON.
        headers: { Accept: "application/json" },
      });

      if (!response.ok) {
        const message = await readFormspreeError(response);
        setStatus("error");
        setErrorMessage(message);
        toast.error(message);
        return;
      }

      // Clear the fields so a second inquiry starts from a blank form rather
      // than silently re-submitting the first one.
      form.reset();
      setStatus("success");
      toast.success(SUCCESS_MESSAGE);
    } catch {
      // Offline, DNS failure, blocked by an extension — the inputs are kept so
      // nothing the visitor typed is lost.
      setStatus("error");
      setErrorMessage(GENERIC_ERROR);
      toast.error(GENERIC_ERROR);
    }
  };

  const submitting = status === "submitting";

  return (
    <footer id="contact" className="overflow-hidden bg-accent text-accent-foreground">
      <div className="mx-auto max-w-[1600px] px-5 py-20 sm:px-8 sm:py-24">
        <div className="grid gap-14 lg:grid-cols-[1.1fr_1fr]">
          <div>
            <h2 className="display section-title heading-flush break-words">Start a Project</h2>

            <p className="label-caps mt-6 max-w-md leading-[2]">
              Tell us what you're building and where it's stuck. We reply to every inquiry within
              two business days.
            </p>
          </div>

          {/* action/method are the no-JS path: the browser posts straight to
              Formspree and lands on its thank-you page. With JS, onSubmit
              intercepts and posts the same FormData over fetch so the visitor
              stays on the page. */}
          <form
            onSubmit={onSubmit}
            action={formEndpoint}
            method="POST"
            className="space-y-5 border-2 border-ink bg-cream p-6 text-ink sm:p-8"
          >
            {/* Names the notification email in the Formspree inbox. */}
            <input type="hidden" name="_subject" value={`New inquiry — ${siteName}`} />
            {/* Honeypot: Formspree discards any submission where this is filled,
                which catches bots that populate every field they find. */}
            <input
              type="text"
              name="_gotcha"
              tabIndex={-1}
              autoComplete="off"
              aria-hidden="true"
              className="hidden"
            />
            <div className="grid gap-5 sm:grid-cols-2">
              <label className="block">
                <span className="label-caps">Name</span>
                <input
                  required
                  name="name"
                  autoComplete="name"
                  data-lpignore="true"
                  className="mt-2 w-full border-b-2 border-ink/25 bg-transparent py-3 text-base outline-none placeholder:text-ink/45 focus:border-accent"
                  placeholder="Jane Doe"
                />
              </label>
              <label className="block">
                <span className="label-caps">Email</span>
                <input
                  required
                  type="email"
                  name="email"
                  autoComplete="email"
                  data-lpignore="true"
                  className="mt-2 w-full border-b-2 border-ink/25 bg-transparent py-3 text-base outline-none placeholder:text-ink/45 focus:border-accent"
                  placeholder="jane@company.com"
                />
              </label>
            </div>
            <label className="block">
              <span className="label-caps">Project</span>
              <textarea
                required
                name="project"
                rows={4}
                data-lpignore="true"
                className="mt-2 w-full resize-none border-b-2 border-ink/25 bg-transparent py-3 text-base outline-none placeholder:text-ink/45 focus:border-accent"
                placeholder="Scope, timing, and budget range"
              />
            </label>
            {/* Wrapped so the status region is not itself a `space-y-5` child:
                as a direct child it collected the 20px gap and stretched the
                form, even though sr-only takes it out of flow. */}
            <div>
              <button
                type="submit"
                disabled={submitting}
                aria-busy={submitting}
                className="label-caps bg-ink px-8 py-4 text-cream transition-opacity hover:opacity-85 disabled:cursor-not-allowed disabled:opacity-70"
              >
                {status === "submitting"
                  ? "Sending…"
                  : status === "success"
                    ? "Inquiry Sent"
                    : "Send Inquiry"}
              </button>
              {/* The toast is the visible confirmation, but it is not reliably
                  announced everywhere — this is the guaranteed one. */}
              <p role="status" aria-live="polite" className="sr-only">
                {status === "success" ? "Inquiry sent. We'll reply within two business days." : ""}
              </p>
              {/* A failed send has to be visible, not just a toast that expires
                  — the visitor's message is still sitting in the form. */}
              {status === "error" && errorMessage ? (
                <p role="alert" className="mt-4 max-w-md text-sm leading-relaxed text-accent">
                  {errorMessage}
                </p>
              ) : null}
            </div>
          </form>
        </div>

        <div className="mt-16 grid gap-10 border-t border-accent-foreground/30 pt-10 sm:mt-20 sm:grid-cols-2 sm:pt-12 lg:grid-cols-4">
          {columns.map((column) => (
            <div key={column.title}>
              <p className="label-caps">{column.title}</p>
              <ul className="mt-2 text-sm">
                {column.items.map((item) => {
                  const label = typeof item === "string" ? item : item.label;
                  return (
                    <li key={label}>
                      {typeof item === "string" ? (
                        // "Omaha, NE" is an address, not a destination — as a
                        // link it was an unlabelled dead end for screen readers.
                        <span className="flex min-h-11 items-center py-2">{label}</span>
                      ) : (
                        <a
                          href={item.href}
                          className="flex min-h-11 items-center py-2 transition-opacity hover:opacity-70"
                        >
                          {label}
                        </a>
                      )}
                    </li>
                  );
                })}
              </ul>

            </div>
          ))}

          {/* Contact is rendered on its own rather than from `columns`: the
              rows pair an icon with their label, and the address is two lines
              of plain text rather than a link. Icons are decorative — the
              mailto/tel links carry their own accessible names. */}
          <div>
            <p className="label-caps">Contact</p>
            <ul className="mt-2 text-sm">
              <li>
                <a
                  href={`mailto:${contact.email}`}
                  className="flex min-h-11 items-center gap-3 py-2 transition-opacity hover:opacity-70"
                >
                  <MailIcon />
                  <span>{contact.email}</span>
                </a>
              </li>
              <li>
                <a
                  href={`tel:${contact.phone}`}
                  className="flex min-h-11 items-center gap-3 py-2 transition-opacity hover:opacity-70"
                >
                  <PhoneIcon />
                  <span>{contact.phoneDisplay}</span>
                </a>
              </li>
              <li>
                {/* A postal address is a fact, not a destination — as a link it
                    was an unlabelled dead end for screen readers. <address> is
                    the element for it; the italic default is cleared because
                    nothing else in this footer is italic. */}
                <address className="flex min-h-11 items-start gap-3 py-2 not-italic leading-relaxed">
                  <PinIcon />
                  <span>
                    {addressLines.map((line) => (
                      <span key={line} className="block">
                        {line}
                      </span>
                    ))}
                  </span>
                </address>
              </li>
            </ul>
          </div>
        </div>

        <div className="mt-16 w-full overflow-hidden sm:mt-20">
          <p
            className="display whitespace-nowrap leading-none opacity-80"
            style={{ fontSize: "clamp(2rem, 9vw, 9rem)" }}
          >
            MADE IN OMAHA
          </p>
        </div>
        <p className="label-caps mt-6">© {new Date().getFullYear()} Brand Ledger</p>
      </div>
    </footer>
  );
}

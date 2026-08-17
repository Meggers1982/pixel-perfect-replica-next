"use client";

import { useState, type FormEvent } from "react";
import { toast } from "sonner";

import { projects } from "@/lib/projects";
import { formEndpoint, siteName } from "@/lib/site";

/** A bare string is a plain fact (no destination); an object is a real link. */
type FooterItem = string | { label: string; href: string };

const columns: { title: string; items: FooterItem[] }[] = [
  {
    title: "Services",
    // These used to point at "#top", which sent visitors back to the masthead
    // and gave crawlers four internal links to nowhere.
    items: ["Brand Identity", "Digital Product", "Positioning", "Packaging"].map((label) => ({
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
  {
    title: "Contact",
    items: [
      { label: "hello@thebrandledger.com", href: "mailto:hello@thebrandledger.com" },
      { label: "(402) 957-2262", href: "tel:+14029572262" },
      "Omaha, NE",
    ],
  },
];

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
            className="space-y-5"
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
                  className="mt-2 w-full border-b border-accent-foreground/70 bg-transparent py-3 text-base outline-none placeholder:text-accent-foreground/75 focus:border-accent-foreground"
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
                  className="mt-2 w-full border-b border-accent-foreground/70 bg-transparent py-3 text-base outline-none placeholder:text-accent-foreground/75 focus:border-accent-foreground"
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
                className="mt-2 w-full resize-none border-b border-accent-foreground/70 bg-transparent py-3 text-base outline-none placeholder:text-accent-foreground/75 focus:border-accent-foreground"
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
                className="label-caps bg-accent-foreground px-8 py-4 text-accent transition-opacity hover:opacity-85 disabled:cursor-not-allowed disabled:opacity-70"
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
                <p role="alert" className="mt-4 max-w-md text-sm leading-relaxed">
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

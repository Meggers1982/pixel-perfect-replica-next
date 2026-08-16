"use client";

import { useState, type FormEvent } from "react";
import { toast } from "sonner";

import { projects } from "@/lib/projects";

type FooterItem = string | { label: string; href: string };

const columns: { title: string; items: FooterItem[] }[] = [
  { title: "Services", items: ["Brand Identity", "Digital Product", "Positioning", "Packaging"] },
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

export function SiteFooter() {
  const [submitted, setSubmitted] = useState(false);

  const onSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSubmitted(true);
    toast.success("Thanks — we'll reply within two business days.");
  };

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

          <form onSubmit={onSubmit} className="space-y-5">
            <div className="grid gap-5 sm:grid-cols-2">
              <label className="block">
                <span className="label-caps">Name</span>
                <input
                  required
                  name="name"
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
            <button
              type="submit"
              className="label-caps bg-accent-foreground px-8 py-4 text-accent transition-opacity hover:opacity-85"
            >
              {submitted ? "Inquiry Sent" : "Send Inquiry"}
            </button>
          </form>
        </div>

        <div className="mt-16 grid gap-10 border-t border-accent-foreground/30 pt-10 sm:mt-20 sm:grid-cols-2 sm:pt-12 lg:grid-cols-4">
          {columns.map((column) => (
            <div key={column.title}>
              <p className="label-caps">{column.title}</p>
              <ul className="mt-2 text-sm">
                {column.items.map((item) => {
                  const label = typeof item === "string" ? item : item.label;
                  const href = typeof item === "string" ? "#top" : item.href;
                  return (
                    <li key={label}>
                      <a
                        href={href}
                        className="flex min-h-11 items-center py-2 transition-opacity hover:opacity-70"
                      >
                        {label}
                      </a>
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

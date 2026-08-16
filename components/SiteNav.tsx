"use client";

import type { MouseEvent } from "react";
import { useCallback, useEffect, useRef, useState } from "react";
import { Menu, X } from "lucide-react";
import { useReducedMotion } from "@/lib/use-reduced-motion";

const links = [
  { href: "#top", label: "Home" },
  { href: "#services", label: "Services" },
  { href: "#work", label: "Work" },
  { href: "#about", label: "About" },
  { href: "#contact", label: "Contact" },
];

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), textarea:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

function getFocusables(container: HTMLElement | null) {
  if (!container) return [];
  return Array.from(container.querySelectorAll<HTMLElement>(FOCUSABLE)).filter(
    (el) => el.offsetParent !== null && !el.hasAttribute("disabled") && el.tabIndex >= 0
  );
}

/** Tracks which section is currently in view so nav items can expose aria-current. */
function useActiveSection() {
  const [active, setActive] = useState<string | null>(null);

  useEffect(() => {
    const ids = links.map((l) => l.href.slice(1));
    const sections = ids
      .map((id) => document.getElementById(id))
      .filter((el): el is HTMLElement => el !== null);
    if (sections.length === 0) return;

    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((e) => e.isIntersecting)
          .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
        if (visible) setActive(`#${visible.target.id}`);
      },
      { rootMargin: "-45% 0px -45% 0px", threshold: [0, 0.25, 0.5, 1] }
    );

    sections.forEach((section) => observer.observe(section));
    return () => observer.disconnect();
  }, []);

  return active;
}

/** True while the viewport is parked at the very top of the document. */
function useAtTop() {
  const [atTop, setAtTop] = useState(true);

  useEffect(() => {
    const update = () => setAtTop(window.scrollY < 80);
    update();
    window.addEventListener("scroll", update, { passive: true });
    window.addEventListener("resize", update);
    return () => {
      window.removeEventListener("scroll", update);
      window.removeEventListener("resize", update);
    };
  }, []);

  return atTop;
}

export function SiteNav() {
  const [open, setOpen] = useState(false);
  const toggleRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLElement>(null);
  const lastFocusedRef = useRef<HTMLElement | null>(null);
  const reducedMotion = useReducedMotion();
  const activeSection = useActiveSection();
  const atTop = useAtTop();

  const isCurrent = useCallback(
    (href: string) => (href === "#top" ? atTop : !atTop && activeSection === href),
    [activeSection, atTop]
  );

  /** Smooth-scrolls to the hero and parks keyboard focus there. */
  const goHome = useCallback(
    (e: MouseEvent<HTMLAnchorElement>) => {
      const hero = document.getElementById("top");
      if (!hero) return;
      e.preventDefault();
      // Focus belongs on the hero, not back on the hamburger toggle.
      lastFocusedRef.current = null;
      setOpen(false);
      window.scrollTo({ top: 0, behavior: reducedMotion ? "auto" : "smooth" });
      hero.setAttribute("tabindex", "-1");
      // Wait for the menu to unmount so its teardown can't steal focus back.
      hero.focus({ preventScroll: true });
      requestAnimationFrame(() =>
        requestAnimationFrame(() => hero.focus({ preventScroll: true }))
      );
      if (window.location.hash !== "#top") {
        window.history.replaceState(null, "", "#top");
      }
    },
    [reducedMotion]
  );


  const close = useCallback(() => setOpen(false), []);

  useEffect(() => {
    if (!open) return;

    // Lock body scroll while the mobile menu is open.
    const originalOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    // Move focus into the menu when it opens.
    const focusables = getFocusables(menuRef.current);
    (focusables[0] ?? menuRef.current)?.focus();

    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        setOpen(false);
        return;
      }

      if (e.key !== "Tab") return;

      const elements = getFocusables(menuRef.current);
      if (elements.length === 0) {
        e.preventDefault();
        return;
      }

      const first = elements[0]!;
      const last = elements[elements.length - 1]!;

      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    };

    // Close (and therefore restore scroll) on rotation / resize past the
    // mobile breakpoint, and on any history navigation.
    const onViewportChange = () => {
      if (window.innerWidth >= 768) setOpen(false);
    };

    window.addEventListener("keydown", onKey);
    window.addEventListener("resize", onViewportChange);
    window.addEventListener("orientationchange", onViewportChange);
    window.addEventListener("popstate", close);

    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("resize", onViewportChange);
      window.removeEventListener("orientationchange", onViewportChange);
      window.removeEventListener("popstate", close);
      // Always restore the original scroll state, whatever closed the menu.
      document.body.style.overflow = originalOverflow;
    };
  }, [open, close]);

  useEffect(() => {
    if (!open) {
      // Return focus to the hamburger toggle when the menu closes.
      lastFocusedRef.current?.focus();
    } else {
      lastFocusedRef.current = toggleRef.current;
    }
  }, [open]);

  // Unmount safety: never leave the body scroll-locked.
  useEffect(() => {
    return () => {
      document.body.style.overflow = "";
    };
  }, []);

  const transition = reducedMotion ? "" : "transition-colors";

  return (
    <header className="fixed inset-x-0 top-0 z-40 bg-ink text-cream">
      <div className="mx-auto grid max-w-[1600px] grid-cols-[minmax(0,1fr)_auto] items-center gap-4 px-5 py-3 sm:px-8">
        <a
          href="#top"
          className="logo-mark inline-flex min-h-11 min-w-0 items-center whitespace-nowrap leading-[0.92]"
          aria-label="Brand Ledger, back to top of page"
          onClick={goHome}
        >
          <span className="whitespace-nowrap">
            Brand <span className="text-accent-on-dark">Ledger</span>
          </span>
        </a>


        <nav className="hidden items-center gap-5 md:flex md:gap-9" aria-label="Desktop">
          {links.map((link) => {
            const current = isCurrent(link.href);
            return (
              <a
                key={link.href}
                href={link.href}
                onClick={link.href === "#top" ? goHome : undefined}
                aria-label={link.href === "#top" ? "Home, back to top of page" : undefined}
                aria-current={current ? "true" : undefined}
                className={`label-caps inline-flex min-h-11 items-center ${transition} hover:text-accent-on-dark ${
                  current ? "text-accent-on-dark" : ""
                }`}

              >
                {link.label}
              </a>
            );
          })}
        </nav>

        <button
          ref={toggleRef}
          type="button"
          onClick={() => setOpen((v) => !v)}
          aria-label={open ? "Close menu" : "Open menu"}
          aria-expanded={open}
          aria-controls="mobile-menu"
          className={`-mr-2 inline-flex h-11 w-11 shrink-0 items-center justify-center text-cream ${transition} hover:text-accent-on-dark md:hidden`}
        >
          {open ? <X className="h-6 w-6" aria-hidden /> : <Menu className="h-6 w-6" aria-hidden />}
        </button>
      </div>

      {open && (
        <>
          <nav
            ref={menuRef}
            id="mobile-menu"
            tabIndex={-1}
            aria-label="Mobile"
            className={`relative z-10 border-t border-cream/15 bg-ink px-5 pb-5 pt-2 outline-none md:hidden ${
              reducedMotion ? "" : "animate-fade-in"
            }`}
          >
            {links.map((link) => {
              const current = isCurrent(link.href);
              return (
                <a
                  key={link.href}
                  href={link.href}
                  onClick={link.href === "#top" ? goHome : close}
                  aria-label={link.href === "#top" ? "Home, back to top of page" : undefined}
                  aria-current={current ? "true" : undefined}
                  className={`label-caps block border-b border-cream/10 py-4 ${transition} last:border-b-0 hover:text-accent-on-dark ${
                    current ? "text-accent-on-dark" : ""
                  }`}
                  tabIndex={0}
                >
                  {link.label}
                  {current && <span className="sr-only"> (current section)</span>}
                </a>
              );
            })}
          </nav>
          <button
            type="button"
            aria-label="Close menu"
            tabIndex={-1}
            onClick={close}
            className="fixed inset-0 top-0 z-0 h-dvh w-full cursor-default bg-ink/60 md:hidden"
          />
        </>
      )}
    </header>
  );
}

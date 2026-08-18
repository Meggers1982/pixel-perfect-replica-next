"use client";

import { useEffect, useRef, useState } from "react";

import {
  CONSENT_STORAGE_KEY as STORAGE_KEY,
  setAnalyticsConsent,
  type ConsentChoice,
} from "@/lib/analytics";

export function CookieBar() {
  const [visible, setVisible] = useState(false);
  const barRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!localStorage.getItem(STORAGE_KEY)) setVisible(true);
  }, []);

  // Keep the fixed bar from permanently covering the bottom of the page.
  useEffect(() => {
    if (!visible) return;
    const bar = barRef.current;
    if (!bar) return;
    const apply = () =>
      document.body.style.setProperty("padding-bottom", `${bar.offsetHeight}px`);
    apply();
    const observer = new ResizeObserver(apply);
    observer.observe(bar);
    return () => {
      observer.disconnect();
      document.body.style.removeProperty("padding-bottom");
    };
  }, [visible]);

  if (!visible) return null;

  // Decline used to only hide the bar. It now reaches GA too, so the choice
  // the banner offers is the choice that actually gets made.
  const dismiss = (value: ConsentChoice) => {
    localStorage.setItem(STORAGE_KEY, value);
    setAnalyticsConsent(value);
    setVisible(false);
  };

  return (
    <div ref={barRef} className="fixed inset-x-0 bottom-0 z-50 bg-ink text-cream">
      <div className="mx-auto flex max-w-[1600px] flex-col gap-4 px-5 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-8">
        <p className="max-w-2xl text-sm text-cream/80">
          We use a small number of cookies to understand how this site is used. Nothing is sold or
          shared.
        </p>
        <div className="flex gap-3">
          <button
            onClick={() => dismiss("declined")}
            className="label-caps inline-flex min-h-11 items-center justify-center border border-cream/50 px-5 py-3 text-cream transition-colors hover:border-cream"
          >
            Decline
          </button>
          <button
            onClick={() => dismiss("accepted")}
            className="label-caps inline-flex min-h-11 items-center justify-center bg-accent px-5 py-3 text-accent-foreground transition-opacity hover:opacity-85"
          >
            Accept
          </button>
        </div>
      </div>
    </div>
  );
}

"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useEffect, useState, type ReactNode } from "react";

export function Providers({ children }: { children: ReactNode }) {
  // One client per browser session; created lazily so it is never shared
  // between requests during SSR.
  const [queryClient] = useState(() => new QueryClient());

  // Flag webfont readiness on <html> so visual-regression runs can wait for the
  // final metrics instead of screenshotting a fallback-rendered frame.
  useEffect(() => {
    const mark = () => document.documentElement.setAttribute("data-fonts-ready", "true");
    if (document.fonts?.status === "loaded") {
      mark();
      return;
    }
    document.fonts?.ready.then(mark).catch(() => mark());
  }, []);

  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

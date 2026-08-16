import nextCoreWebVitals from "eslint-config-next/core-web-vitals";
import nextTypescript from "eslint-config-next/typescript";
import prettier from "eslint-config-prettier";

const config = [
  {
    ignores: [".next/**", "out/**", "node_modules/**", "next-env.d.ts", "tests/**"],
  },
  ...nextCoreWebVitals,
  ...nextTypescript,
  prettier,
  {
    rules: {
      // Every image is a plain <img> against /public on purpose — see next.config.ts.
      "@next/next/no-img-element": "off",

      // The rules below flag patterns carried over verbatim from the TanStack
      // Start build. They are deliberate there and the Playwright suite pins the
      // behaviour they produce, so they are warnings rather than errors: worth
      // revisiting as a follow-up, not worth failing a build over today.
      //
      //   set-state-in-effect — the "start SSR-safe, sync after mount" hooks
      //     (useReducedMotion, useReducedData, useIsMobile, CookieBar, WorkImage).
      //   refs — FeaturedWork mirrors the open index into a ref during render so
      //     the lightbox can restore focus to the right card after it closes.
      //   purity — shadcn's sidebar.tsx, untouched from the registry.
      "react-hooks/set-state-in-effect": "warn",
      "react-hooks/refs": "warn",
      "react-hooks/purity": "warn",
      "react/no-unescaped-entities": "warn",
    },
  },
];

export default config;

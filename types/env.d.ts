/**
 * Declaring the variable as a real property (rather than letting it fall
 * through ProcessEnv's index signature) does two things: it satisfies
 * `noPropertyAccessFromIndexSignature`, and it keeps the access written as
 * `process.env.NEXT_PUBLIC_SITE_URL` — the literal form Next replaces at build
 * time. Bracket notation would not be inlined into a client bundle.
 */
declare namespace NodeJS {
  interface ProcessEnv {
    /** Origin the site is served from, e.g. https://thebrandledger.com. */
    NEXT_PUBLIC_SITE_URL?: string;
    /** Formspree form URL the contact form posts to. */
    NEXT_PUBLIC_FORMSPREE_ENDPOINT?: string;
  }
}

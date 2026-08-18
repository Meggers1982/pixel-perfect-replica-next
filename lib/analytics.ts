/**
 * GA4 wiring.
 *
 * The site shows a cookie bar with a real Decline button, so the tag is
 * installed behind Google Consent Mode rather than fired on load: analytics
 * storage defaults to denied, and only an explicit Accept flips it to granted.
 * Declining leaves it denied, which is what the banner already promises.
 *
 * gtag.js still loads either way — under denied consent it sends cookieless
 * pings and writes nothing to the browser, which is how Consent Mode is meant
 * to be deployed.
 */
export const GA_MEASUREMENT_ID = "G-09TDRM4HQ8";

/** Shared with CookieBar — the key the visitor's choice is stored under. */
export const CONSENT_STORAGE_KEY = "nb-cookie-consent";

export type ConsentChoice = "accepted" | "declined";

/**
 * Push the visitor's choice to gtag. Safe before gtag.js has finished loading:
 * the stub in the consent script queues onto dataLayer, and the tag replays the
 * queue once it arrives.
 */
export function setAnalyticsConsent(choice: ConsentChoice): void {
  if (typeof window === "undefined" || typeof window.gtag !== "function") return;
  window.gtag("consent", "update", {
    analytics_storage: choice === "accepted" ? "granted" : "denied",
  });
}

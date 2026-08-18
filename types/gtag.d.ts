/**
 * Minimal gtag surface — only the three command forms this site issues.
 *
 * The global is created by the inline consent script in components/Analytics,
 * before gtag.js loads, so it is declared optional: anything calling it has to
 * check first (see setAnalyticsConsent in lib/analytics).
 */
type GtagConsentFields = {
  ad_storage?: "granted" | "denied";
  ad_user_data?: "granted" | "denied";
  ad_personalization?: "granted" | "denied";
  analytics_storage?: "granted" | "denied";
};

interface Gtag {
  (command: "js", value: Date): void;
  (command: "config", targetId: string, params?: Record<string, unknown>): void;
  (command: "consent", action: "default" | "update", fields: GtagConsentFields): void;
  (command: "event", eventName: string, params?: Record<string, unknown>): void;
}

interface Window {
  dataLayer?: unknown[];
  gtag?: Gtag;
}

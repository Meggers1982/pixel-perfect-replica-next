import Script from "next/script";

import { CONSENT_STORAGE_KEY, GA_MEASUREMENT_ID } from "@/lib/analytics";

/**
 * Google Analytics 4 (gtag.js), gated by Consent Mode.
 *
 * Three scripts, and the order between the first and the rest is the whole
 * point:
 *
 *  1. `ga-consent-default` runs before anything else and sets every storage
 *     type to denied, then re-grants analytics if this visitor already
 *     accepted on a previous visit. Consent defaults are only honoured if they
 *     are on dataLayer *before* the tag reads them, which is why this is inline
 *     and `beforeInteractive` rather than part of the config script.
 *  2. gtag.js itself, deferred to `afterInteractive` so it never competes with
 *     the first render.
 *  3. The usual `js` / `config` pair.
 *
 * A visitor who has not chosen yet, or who declined, is measured under denied
 * consent — cookieless pings, no identifiers stored on the device. CookieBar
 * calls setAnalyticsConsent to flip this the moment they press Accept.
 */
export function Analytics() {
  return (
    <>
      <Script
        id="ga-consent-default"
        strategy="beforeInteractive"
        dangerouslySetInnerHTML={{
          __html: `
window.dataLayer = window.dataLayer || [];
function gtag(){dataLayer.push(arguments);}
window.gtag = gtag;
gtag('consent', 'default', {
  ad_storage: 'denied',
  ad_user_data: 'denied',
  ad_personalization: 'denied',
  analytics_storage: 'denied'
});
try {
  if (localStorage.getItem('${CONSENT_STORAGE_KEY}') === 'accepted') {
    gtag('consent', 'update', { analytics_storage: 'granted' });
  }
} catch (e) {}
`.trim(),
        }}
      />
      <Script
        id="ga-tag"
        strategy="afterInteractive"
        src={`https://www.googletagmanager.com/gtag/js?id=${GA_MEASUREMENT_ID}`}
      />
      <Script
        id="ga-config"
        strategy="afterInteractive"
        dangerouslySetInnerHTML={{
          __html: `
gtag('js', new Date());
gtag('config', '${GA_MEASUREMENT_ID}');
`.trim(),
        }}
      />
    </>
  );
}

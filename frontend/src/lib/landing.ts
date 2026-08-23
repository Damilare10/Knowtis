import { Capacitor } from "@capacitor/core";

/**
 * The marketing landing page is a standalone HTML/CSS document, not a React route.
 *
 * It lives at `frontend/public/landing.html` (with `frontend/public/landing.css`), so it is
 * served verbatim by `next dev` and copied as-is into `out/` by the static export. Because it
 * is a plain static file rather than an App Router page, Next.js cannot render it from a
 * `page.tsx`; the web-facing routes redirect to it instead.
 *
 * `next.config.ts` sets `output: "export"`, and `redirects()` / `rewrites()` are not applied to
 * a static export, so the redirect has to happen on the client.
 */
export const LANDING_URL = "/landing.html";

/**
 * True when running inside the Capacitor WebView.
 *
 * `NEXT_PUBLIC_IS_CAPACITOR` covers native builds where the bridge has not finished injecting
 * `window.Capacitor` yet; `Capacitor.isNativePlatform()` covers the runtime case.
 */
function isNativePlatform(): boolean {
  return (
    process.env.NEXT_PUBLIC_IS_CAPACITOR === "true" || Capacitor.isNativePlatform()
  );
}

/**
 * Send a web visitor to the static landing page. Returns whether it navigated.
 *
 * Returns `false` without navigating on native, and callers must route somewhere in-app
 * instead. The landing page is web-only marketing: it is excluded from the native bundle by
 * `scripts/strip-web-only-assets.js`, and it has no link back into the app, so sending the
 * Capacitor WebView there would strand the user on a dead end. Guarding here rather than at
 * each call site keeps that invariant enforceable.
 *
 * Uses `location.replace` rather than the Next router because the target is outside the App
 * Router's route tree, and `replace` keeps it out of session history so Back does not bounce
 * the user between the redirect and the landing page.
 */
export function redirectToLanding(): boolean {
  if (typeof window === "undefined") return false;
  if (isNativePlatform()) return false;
  window.location.replace(LANDING_URL);
  return true;
}

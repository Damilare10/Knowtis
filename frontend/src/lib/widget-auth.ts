import { registerPlugin } from '@capacitor/core';
import { apiClient } from './api';

/**
 * Bridges the auth token + API base URL from the web app into native
 * Android SharedPreferences so the home-screen AppWidget can fetch the
 * user's live academic updates. This is a no-op outside the Capacitor
 * Android runtime (web dev / iOS), because the plugin resolves to a
 * no-availability proxy on web.
 *
 * The native plugin is `WidgetAuth` (WidgetAuthPlugin.java), registered
 * in MainActivity. It writes to SharedPreferences `knowtis_widget_prefs`,
 * which KnowtisWidgetProvider reads at update time.
 */

interface WidgetAuthPlugin {
  saveAuth: (opts: { token: string; baseUrl?: string }) => Promise<{ saved: boolean }>;
  clearAuth: () => Promise<{ cleared: boolean }>;
  refreshWidget: () => Promise<{ refreshed: boolean }>;
}

const WidgetAuth = registerPlugin<WidgetAuthPlugin>('WidgetAuth');

const baseUrlFallback =
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  (apiClient.defaults.baseURL as string | undefined) ||
  undefined;

export function persistWidgetAuth(token: string): void {
  WidgetAuth
    .saveAuth({ token, baseUrl: baseUrlFallback })
    .catch(() => { /* non-fatal: web/SSR or plugin unavailable */ });
}

export function clearWidgetAuth(): void {
  WidgetAuth
    .clearAuth()
    .catch(() => { /* non-fatal */ });
}

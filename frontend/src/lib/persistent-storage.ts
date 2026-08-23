import { Preferences } from '@capacitor/preferences';

/**
 * Universal persistent storage helper for Knowtis App.
 * Combines localStorage with @capacitor/preferences (Android/iOS SharedPreferences)
 * so auth tokens, refresh tokens, and onboarding states survive Android WebView
 * memory clears, app restarts, and background kills.
 */

export async function setPersistentItem(key: string, value: string): Promise<void> {
  if (typeof window !== 'undefined') {
    try {
      localStorage.setItem(key, value);
    } catch (e) {
      console.warn('localStorage.setItem failed:', e);
    }
  }
  try {
    await Preferences.set({ key, value });
  } catch (e) {
    // Non-fatal on web/SSR
  }
}

export async function getPersistentItem(key: string): Promise<string | null> {
  let val: string | null = null;

  if (typeof window !== 'undefined') {
    try {
      val = localStorage.getItem(key);
    } catch (e) {
      console.warn('localStorage.getItem failed:', e);
    }
  }

  if (val !== null && val !== undefined) {
    return val;
  }

  try {
    const { value } = await Preferences.get({ key });
    if (value !== null && value !== undefined) {
      if (typeof window !== 'undefined') {
        try {
          localStorage.setItem(key, value);
        } catch (e) {}
      }
      return value;
    }
  } catch (e) {}

  return null;
}

export async function removePersistentItem(key: string): Promise<void> {
  if (typeof window !== 'undefined') {
    try {
      localStorage.removeItem(key);
    } catch (e) {
      console.warn('localStorage.removeItem failed:', e);
    }
  }
  try {
    await Preferences.remove({ key });
  } catch (e) {}
}

export function getPersistentItemSync(key: string): string | null {
  if (typeof window !== 'undefined') {
    try {
      return localStorage.getItem(key);
    } catch (e) {}
  }
  return null;
}

/*
Native Notification Utility for Knowtis Android & Mobile App
Manages Capacitor Local Notifications, Push Notifications, and Android Notification Channels.
Ensures alerts pop up on the native Android status bar.
*/
import { Capacitor } from '@capacitor/core';
import { LocalNotifications } from '@capacitor/local-notifications';
import { PushNotifications } from '@capacitor/push-notifications';
import { Preferences } from '@capacitor/preferences';

const SHOWN_NOTIFS_KEY = 'knowtis_shown_native_notifs';

/**
 * Generate a consistent 32-bit positive integer hash from a string ID for Capacitor LocalNotifications.
 */
function hashStringToId(str: string): number {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    const char = str.charCodeAt(i);
    hash = (hash << 5) - hash + char;
    hash |= 0; // Convert to 32bit integer
  }
  return Math.abs(hash) || Math.floor(Math.random() * 100000);
}

/**
 * Get the set of notification IDs that have already been popped up on the status bar.
 */
async function getShownNotificationIds(): Promise<Set<string>> {
  try {
    if (Capacitor.isNativePlatform()) {
      const { value } = await Preferences.get({ key: SHOWN_NOTIFS_KEY });
      if (value) {
        return new Set(JSON.parse(value));
      }
    } else if (typeof window !== 'undefined') {
      const raw = localStorage.getItem(SHOWN_NOTIFS_KEY);
      if (raw) return new Set(JSON.parse(raw));
    }
  } catch (err) {
    console.warn('Failed to load shown notification IDs:', err);
  }
  return new Set();
}

/**
 * Record a notification ID as shown on the native status bar.
 */
async function markNotificationAsShown(id: string): Promise<void> {
  try {
    const set = await getShownNotificationIds();
    set.add(id);
    const arr = Array.from(set);
    // Keep max 500 recent IDs
    const trimmed = arr.slice(-500);
    const json = JSON.stringify(trimmed);

    if (Capacitor.isNativePlatform()) {
      await Preferences.set({ key: SHOWN_NOTIFS_KEY, value: json });
    } else if (typeof window !== 'undefined') {
      localStorage.setItem(SHOWN_NOTIFS_KEY, json);
    }
  } catch (err) {
    console.warn('Failed to save shown notification ID:', err);
  }
}

/**
 * Initialize native Android Notification Channels & permissions on app startup.
 */
export async function initNativeNotifications(
  onFcmTokenReceived?: (token: string) => void
): Promise<void> {
  if (!Capacitor.isNativePlatform()) {
    return;
  }

  try {
    // 1. Create Android Notification Channel for urgent academic alerts
    if (Capacitor.getPlatform() === 'android') {
      await LocalNotifications.createChannel({
        id: 'academic_alerts',
        name: 'Academic Alerts & Reminders',
        description: 'Urgent academic deadline alerts and scheduled reminders',
        importance: 5, // High importance -> heads-up status bar popup + sound
        visibility: 1, // Public on lockscreen
        sound: 'beep.wav',
        vibration: true,
        lights: true,
        lightColor: '#FF5A36',
      });
    }

    // 2. Request Local Notification permissions
    const localPerm = await LocalNotifications.checkPermissions();
    if (localPerm.display !== 'granted') {
      await LocalNotifications.requestPermissions();
    }

    // 3. Register Push Notifications (FCM / APNs)
    const pushPerm = await PushNotifications.checkPermissions();
    if (pushPerm.receive !== 'granted') {
      const req = await PushNotifications.requestPermissions();
      if (req.receive === 'granted') {
        await PushNotifications.register();
      }
    } else {
      await PushNotifications.register();
    }

    // Listen for FCM token registration
    PushNotifications.addListener('registration', (token) => {
      console.log('FCM Token registered:', token.value);
      if (onFcmTokenReceived) {
        onFcmTokenReceived(token.value);
      }
    });

    PushNotifications.addListener('registrationError', (error) => {
      console.error('FCM Token registration error:', error);
    });

    // Listen for push notifications received while app is in foreground
    PushNotifications.addListener('pushNotificationReceived', async (notification) => {
      console.log('Push notification received in foreground:', notification);
      // Trigger a local notification so it pops up on the status bar even when in foreground
      await popNativeStatusBarAlert({
        id: notification.id || String(Date.now()),
        title: notification.title || 'Knowtis Alert',
        body: notification.body || '',
      });
    });

    // Listen for notification tap actions (when user taps a background push notification)
    PushNotifications.addListener('pushNotificationActionPerformed', (notification) => {
      console.log('Push notification action performed (tapped in background):', notification);
    });
  } catch (err) {
    console.error('Failed to initialize native notifications:', err);
  }
}

/**
 * Trigger a native Android status bar pop-up notification immediately.
 */
export async function popNativeStatusBarAlert(params: {
  id: string;
  title: string;
  body: string;
  extra?: Record<string, unknown>;
}): Promise<boolean> {
  const { id, title, body, extra } = params;

  try {
    const shown = await getShownNotificationIds();
    if (shown.has(id)) {
      return false; // Already shown on status bar
    }

    if (Capacitor.isNativePlatform()) {
      const numericId = hashStringToId(id);
      await LocalNotifications.schedule({
        notifications: [
          {
            id: numericId,
            title: title || 'Academic Alert',
            body: body || 'You have a new alert in Knowtis',
            smallIcon: 'ic_stat_k_outline',
            channelId: 'academic_alerts',
            schedule: { at: new Date(Date.now() + 150) },
            extra: extra || null,
          },
        ],
      });
      await markNotificationAsShown(id);
      return true;
    }
  } catch (err) {
    console.error('Error triggering native status bar alert:', err);
  }
  return false;
}

/**
 * Schedule a native local reminder at a specific future date/time.
 */
export async function scheduleNativeLocalReminder(params: {
  id: string;
  title: string;
  body: string;
  scheduledAt: Date;
}): Promise<boolean> {
  const { id, title, body, scheduledAt } = params;

  if (!Capacitor.isNativePlatform()) return false;

  try {
    const numericId = hashStringToId(id);
    await LocalNotifications.schedule({
      notifications: [
        {
          id: numericId,
          title: title || 'Upcoming Academic Reminder',
          body: body || 'Reminder from Knowtis',
          smallIcon: 'ic_stat_k_outline',
          channelId: 'academic_alerts',
          schedule: { at: scheduledAt },
        },
      ],
    });
    return true;
  } catch (err) {
    console.error('Error scheduling native local reminder:', err);
    return false;
  }
}

/**
 * Sync fresh unread notifications from backend with the native Android status bar.
 * Fires a native status bar notification popup for any new unread alerts.
 */
export async function syncInAppNotificationsToNativeStatusBar(
  items: Array<{ id: string; title: string; description: string; is_read?: boolean }>
): Promise<void> {
  if (!items || items.length === 0) return;

  const shown = await getShownNotificationIds();

  for (const item of items) {
    if (!item.is_read && !shown.has(item.id)) {
      await popNativeStatusBarAlert({
        id: item.id,
        title: item.title,
        body: item.description,
      });
    }
  }
}

/*
Zustand State Store for Knowtis Frontend
Wired to the real backend API. No dev mock user fallback.
*/
import { create } from 'zustand';
import { authApi, eventsApi, remindersApi, whatsappApi, notificationsApi, aiApi, widgetApi, billingApi, trainingApi, type ChatMessage } from './api';
import { persistWidgetAuth, clearWidgetAuth } from './widget-auth';
import { initNativeNotifications, syncInAppNotificationsToNativeStatusBar } from './native-notifications';
import { setPersistentItem, getPersistentItem, removePersistentItem, getPersistentItemSync } from './persistent-storage';
import { Preferences } from '@capacitor/preferences';
import type { AcademicEvent, EventType } from './events';

export type { AcademicEvent, EventType };

interface User {
  id: string;
  email: string;
  username: string;
  full_name: string;
  is_premium: boolean;
  tier: string;
  role?: string;
  created_at?: string;
  whatsapp_number?: string;
  ai_tokens_received?: number;
  notification_advance_hours?: number;
}

interface WhatsAppGroup {
  id: string;
  group_name: string;
  group_jid: string;
  coverage_state: 'ACTIVE' | 'DEGRADED' | 'PAUSED' | 'RECOVERING';
  join_date: string;
  is_active: boolean;
  monitored_keywords?: string[];
  monitored_courses?: string[];
  filter_mode?: 'ALL' | 'FILTERED';
}

interface Reminder {
  id: string;
  event_id: string;
  scheduled_time?: string;
  is_sent: boolean;
  delivery_channel: string;
  event?: AcademicEvent;
}

interface NotificationItem {
  id: string;
  title: string;
  description: string;
  is_read: boolean;
  created_at: string;
  event?: AcademicEvent;
}

interface NightBrief {
  summary: string;
  deadline_count: number;
  alert_count: number;
  event_count: number;
  upcoming_deadlines: AcademicEvent[];
  active_alerts: AcademicEvent[];
}

type AuthCredentials = { username: string; password: string };
type RegisterPayload = {
  email: string;
  username: string;
  password: string;
  confirm_password: string;
  whatsapp_number?: string;
};
type EventFilters = { skip?: number; limit?: number; event_type?: string; course_code?: string };
type EventPayload = Partial<AcademicEvent> & Record<string, unknown>;

function getErrorMessage(err: unknown, fallback: string): string {
  if (typeof err === 'object' && err !== null && 'response' in err) {
    const res = (err as { response?: { data?: { detail?: unknown; message?: unknown } } }).response;
    const detail = res?.data?.detail ?? res?.data?.message;
    if (typeof detail === 'string') {
      return detail;
    }
    if (Array.isArray(detail)) {
      const msgs = detail
        .map((item) => {
          if (typeof item === 'object' && item !== null && 'msg' in item) {
            return String((item as { msg: unknown }).msg);
          }
          return typeof item === 'string' ? item : '';
        })
        .filter(Boolean);
      if (msgs.length > 0) return msgs.join('. ');
    }
    if (typeof detail === 'object' && detail !== null) {
      if ('msg' in detail && typeof (detail as { msg: unknown }).msg === 'string') {
        return (detail as { msg: string }).msg;
      }
      return JSON.stringify(detail);
    }
  }
  if (err instanceof Error) {
    return err.message;
  }
  return fallback;
}

function normalizeUser(raw: Record<string, unknown>): User {
  return {
    id: String(raw.id ?? ''),
    email: String(raw.email ?? ''),
    username: String(raw.username ?? ''),
    full_name: String(raw.full_name ?? raw.username ?? 'Student'),
    is_premium: Boolean(raw.is_premium ?? raw.tier === 'premium'),
    tier: String(raw.tier ?? 'free'),
    role: raw.role ? String(raw.role) : undefined,
    created_at: raw.created_at ? String(raw.created_at) : undefined,
    whatsapp_number: raw.whatsapp_number ? String(raw.whatsapp_number) : undefined,
    notification_advance_hours: typeof raw.notification_advance_hours === 'number' ? raw.notification_advance_hours : 3,
  };
}

interface AppState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  hasHydrated: boolean;
  loading: boolean;
  error: string | null;

  events: AcademicEvent[];
  totalEvents: number;
  eventsTruncated: boolean;
  eventsPlanLimit: number | null;

  groups: WhatsAppGroup[];
  reminders: Reminder[];

  notifications: NotificationItem[];
  unreadNotificationCount: number;
  nightBrief: NightBrief | null;

  // AI conversation (persisted server-side, mirrored in-store for the UI)
  aiMessages: ChatMessage[];
  aiHistoryLoading: boolean;
  aiSending: boolean;
  aiChatError: string | null;
  aiClearing: boolean;

  // AI reveal overlay (persists across the route change to /ai).
  aiReveal: { cx: number; cy: number; id: number } | null;
  startAiReveal: (cx: number, cy: number) => void;
  endAiReveal: () => void;

  // AI Popup Assistant
  aiPopupOpen: boolean;
  setAiPopupOpen: (open: boolean) => void;

  // Actions
  login: (credentials: AuthCredentials) => Promise<boolean>;
  register: (data: RegisterPayload) => Promise<boolean>;
  logout: () => void;
  checkAuth: () => Promise<void>;

  fetchEvents: (filters?: EventFilters) => Promise<void>;
  createEvent: (data: EventPayload) => Promise<boolean>;
  updateEvent: (id: string, patch: Partial<AcademicEvent>) => Promise<boolean>;
  confirmEvent: (id: string) => Promise<boolean>;
  dismissEvent: (id: string) => Promise<boolean>;
  deleteEvent: (id: string) => Promise<void>;

  fetchGroups: () => Promise<void>;
  joinGroup: (inviteLink: string) => Promise<boolean>;
  unlinkGroup: (id: string) => Promise<void>;
  updateGroupFilters: (id: string, data: { monitored_keywords?: string[]; monitored_courses?: string[]; filter_mode?: string }) => Promise<boolean>;

  fetchReminders: () => Promise<void>;
  createReminder: (eventId: string, daysBefore?: number) => Promise<boolean>;
  dismissReminder: (id: string) => Promise<void>;

  fetchNotifications: () => Promise<void>;
  fetchUnreadCount: () => Promise<void>;
  markNotificationRead: (id: string) => Promise<void>;
  fetchNightBrief: () => Promise<void>;
  fetchAIHistory: () => Promise<void>;
  sendAIMessage: (text: string) => Promise<void>;
  clearAIChat: () => Promise<boolean>;
  clearAIChatError: () => void;
  clearError: () => void;
  updateProfile: (data: Record<string, unknown>) => Promise<boolean>;
  deleteAccount: () => Promise<boolean>;
  upgradeToPremium: (tier: string) => Promise<boolean>;
  widgetData: any | null;
  fetchWidgetData: () => Promise<void>;
  activeSubscription: any | null;
  fetchActiveSubscription: () => Promise<void>;
}

export const useAppStore = create<AppState>((set, get) => ({
  user: null,
  token: null,
  isAuthenticated: false,
  hasHydrated: false,
  loading: false,
  error: null,

  events: [],
  totalEvents: 0,
  eventsTruncated: false,
  eventsPlanLimit: null,

  groups: [],
  reminders: [],

  notifications: [],
  unreadNotificationCount: 0,
  nightBrief: null,
  widgetData: null,
  activeSubscription: null,

  aiMessages: [],
  aiHistoryLoading: false,
  aiSending: false,
  aiChatError: null,
  aiClearing: false,

  aiReveal: null,
  startAiReveal: (cx, cy) => set({ aiReveal: { cx, cy, id: Date.now() } }),
  endAiReveal: () => set({ aiReveal: null }),

  aiPopupOpen: false,
  setAiPopupOpen: (open) => set({ aiPopupOpen: open }),

  clearError: () => set({ error: null }),

  clearAIChatError: () => set({ aiChatError: null }),

  // Authentication Actions
  login: async (credentials) => {
    set({ loading: true, error: null });
    try {
      const response = await authApi.login(credentials);
      const { access_token, refresh_token, user } = response.data;
      const normalizedUser = normalizeUser(user as Record<string, unknown>);
      await setPersistentItem('knowtis_token', access_token);
      await setPersistentItem('knowtis_user', JSON.stringify(normalizedUser));
      if (refresh_token) {
        await setPersistentItem('knowtis_refresh_token', refresh_token);
      }
      persistWidgetAuth(access_token);
      set({
        token: access_token,
        user: normalizedUser,
        isAuthenticated: true,
        loading: false,
      });

      get().fetchGroups();
      get().fetchEvents();
      get().fetchNotifications();
      get().fetchUnreadCount();
      try {
        initNativeNotifications((fcmToken) => {
          authApi.updateProfile({ fcm_token: fcmToken }).catch(() => {});
        });
      } catch { /* non-fatal */ }
      return true;
    } catch (err: unknown) {
      set({
        loading: false,
        error: getErrorMessage(err, 'Failed to login. Please check credentials.'),
      });
      return false;
    }
  },

  register: async (data) => {
    set({ loading: true, error: null });
    try {
      const response = await authApi.register(data);
      const { access_token, refresh_token, user } = response.data;
      const normalizedUser = normalizeUser(user as Record<string, unknown>);
      await setPersistentItem('knowtis_token', access_token);
      await setPersistentItem('knowtis_user', JSON.stringify(normalizedUser));
      if (refresh_token) {
        await setPersistentItem('knowtis_refresh_token', refresh_token);
      }
      persistWidgetAuth(access_token);
      set({
        token: access_token,
        user: normalizedUser,
        isAuthenticated: true,
        loading: false,
      });

      get().fetchGroups();
      get().fetchEvents();
      get().fetchNotifications();
      get().fetchUnreadCount();
      try {
        initNativeNotifications((fcmToken) => {
          authApi.updateProfile({ fcm_token: fcmToken }).catch(() => {});
        });
      } catch { /* non-fatal */ }
      return true;
    } catch (err: unknown) {
      set({
        loading: false,
        error: getErrorMessage(err, 'Registration failed. Try again.'),
      });
      return false;
    }
  },

  logout: () => {
    removePersistentItem('knowtis_token');
    removePersistentItem('knowtis_refresh_token');
    removePersistentItem('knowtis_user');
    // keep knowtis_onboarded - it marks device as having completed onboarding
    clearWidgetAuth();
    set({
      user: null,
      token: null,
      isAuthenticated: false,
      events: [],
      totalEvents: 0,
      groups: [],
      reminders: [],
      notifications: [],
      unreadNotificationCount: 0,
      nightBrief: null,
      widgetData: null,
      activeSubscription: null,
      error: null,
    });
  },

  checkAuth: async () => {
    if (typeof window === 'undefined') return;

    // 1. IMMEDIATE: Try synchronous localStorage first (instant)
    let token = getPersistentItemSync('knowtis_token');
    let user: User | null = null;

    if (token) {
      try {
        const userStr = localStorage.getItem('knowtis_user');
        if (userStr) {
          user = JSON.parse(userStr) as User;
        }
      } catch { /* ignore parse errors */ }
    }

    // 2. If no token in localStorage, try async Preferences (Capacitor)
    if (!token) {
      token = await getPersistentItem('knowtis_token');
      if (token) {
        try {
          const userStr = await Preferences.get({ key: 'knowtis_user' });
          if (userStr.value) {
            user = JSON.parse(userStr.value) as User;
          }
        } catch { /* ignore */ }
      }
    }

    // 3. INSTANT HYDRATION: Set authenticated state immediately if we have token
    set({
      token,
      user,
      isAuthenticated: !!token,
      hasHydrated: true,
      loading: false,
    });

    if (token) {
      try {
        initNativeNotifications((fcmToken) => {
          authApi.updateProfile({ fcm_token: fcmToken }).catch(() => {});
        });
      } catch { /* ignore */ }
    }

    // 4. NO TOKEN? We're done - stay unauthenticated
    if (!token) {
      set({ isAuthenticated: false, user: null });
      return;
    }

    // 5. BACKGROUND VALIDATION: Probe backend silently
    // Race against 8s timeout; never block UI
    const probe = (async () => {
      try {
        const response = await authApi.getCurrentUser();
        return { ok: true as const, response };
      } catch (err) {
        return { ok: false as const, reason: 'error', err };
      }
    })();
    const ceiling = new Promise<{ ok: false; reason: 'timeout' }>((resolve) =>
      setTimeout(() => resolve({ ok: false, reason: 'timeout' }), 8000),
    );

    const result = await Promise.race([probe, ceiling]);

    if (result.ok) {
      // Token valid - update user with fresh data
      set({
        user: normalizeUser(result.response.data as Record<string, unknown>),
        isAuthenticated: true,
      });
      // Background refresh (non-blocking)
      try { await get().fetchGroups(); } catch { /* non-fatal */ }
      try { await get().fetchEvents(); } catch { /* non-fatal */ }
      try { await get().fetchNotifications(); } catch { /* non-fatal */ }
      try { await get().fetchUnreadCount(); } catch { /* non-fatal */ }
      try {
        initNativeNotifications((fcmToken) => {
          authApi.updateProfile({ fcm_token: fcmToken }).catch(() => {});
        });
      } catch { /* non-fatal */ }
      return;
    }

    if (result.reason === 'error') {
      const status = (result.err as { response?: { status?: number } })?.response?.status;
      if (status === 401) {
        // ONLY redirect on explicit 401 (token expired/revoked)
        await removePersistentItem('knowtis_token');
        await removePersistentItem('knowtis_refresh_token');
        await removePersistentItem('knowtis_user');
        clearWidgetAuth();
        set({ user: null, token: null, isAuthenticated: false });
      } else {
        // Network error / 5xx - KEEP local session (offline mode)
        set({ isAuthenticated: true });
      }
    } else {
      // Timeout - KEEP local session (offline mode)
      set({ isAuthenticated: true });
    }
  },

  // Events Actions
  fetchEvents: async (filters) => {
    try {
      const response = await eventsApi.list(filters);
      const items = (response.data.items || []) as AcademicEvent[];
      set({
        events: items,
        totalEvents: response.data.total ?? items.length,
        eventsTruncated: Boolean(response.data.truncated),
        eventsPlanLimit: response.data.plan_limit ?? null,
      });
    } catch (err) {
      console.error('Failed to fetch events', err);
    }
  },

  createEvent: async (data) => {
    try {
      await eventsApi.create(data);
      get().fetchEvents();
      return true;
    } catch (err: unknown) {
      set({ error: getErrorMessage(err, 'Failed to create event.') });
      return false;
    }
  },

  updateEvent: async (id, patch) => {
    try {
      const response = await eventsApi.update(id, patch as Record<string, unknown>);
      const updated = response.data as AcademicEvent;
      set((state) => ({
        events: state.events.map((e) => (e.id === id ? { ...e, ...updated, needs_review: false } : e)),
      }));
      return true;
    } catch (err: unknown) {
      set({ error: getErrorMessage(err, 'Failed to update event.') });
      return false;
    }
  },

  confirmEvent: async (id) => {
    // Optimistic update
    set((state) => ({
      events: state.events.map((e) => (e.id === id ? { ...e, needs_review: false } : e)),
    }));
    try {
      await trainingApi.submitFeedback({
        academic_event_id: id,
        feedback_type: 'confirmed_correct',
      });
      return true;
    } catch (err) {
      console.error('Failed to confirm event', err);
      return false;
    }
  },

  dismissEvent: async (id) => {
    // Optimistically remove from list
    set((state) => ({
      events: state.events.filter((e) => e.id !== id),
      totalEvents: Math.max(0, state.totalEvents - 1),
    }));
    try {
      await trainingApi.submitFeedback({
        academic_event_id: id,
        feedback_type: 'reported_noise',
      });
      await eventsApi.delete(id);
      return true;
    } catch (err) {
      console.error('Failed to dismiss event', err);
      return false;
    }
  },

  deleteEvent: async (id) => {
    try {
      await eventsApi.delete(id);
      get().fetchEvents();
    } catch (err) {
      console.error('Failed to delete event', err);
    }
  },

  // Groups Actions
  fetchGroups: async () => {
    try {
      const response = await whatsappApi.list();
      set({ groups: (response.data || []) as WhatsAppGroup[] });
    } catch (err) {
      console.error('Failed to fetch groups', err);
    }
  },

  joinGroup: async (inviteLink) => {
    set({ loading: true, error: null });
    try {
      await whatsappApi.join({ invite_link: inviteLink });
      await get().fetchGroups();
      set({ loading: false });
      return true;
    } catch (err: unknown) {
      set({
        loading: false,
        error: getErrorMessage(err, 'Failed to request group join.'),
      });
      return false;
    }
  },

  unlinkGroup: async (id) => {
    try {
      await whatsappApi.unlink(id);
      get().fetchGroups();
    } catch (err) {
      console.error('Failed to unlink group', err);
    }
  },

  updateGroupFilters: async (id, data) => {
    try {
      await whatsappApi.updateFilters(id, data);
      await get().fetchGroups();
      return true;
    } catch (err: unknown) {
      set({ error: getErrorMessage(err, 'Failed to update group filters.') });
      return false;
    }
  },

  // Reminders Actions
  fetchReminders: async () => {
    try {
      const response = await remindersApi.list();
      const apiReminders = (response.data || []) as Omit<Reminder, 'event'>[];

      // Backend ReminderResponse has no nested event — hydrate from the events list.
      const events = get().events;
      const reminders: Reminder[] = apiReminders.map((r) => ({
        ...r,
        event: events.find((e) => e.id === r.event_id),
      }));

      set({ reminders });
    } catch (err) {
      console.error('Failed to fetch reminders', err);
    }
  },

  createReminder: async (eventId, daysBefore = 1) => {
    try {
      await remindersApi.create({ event_id: eventId, days_before: daysBefore });
      get().fetchReminders();
      return true;
    } catch (err: unknown) {
      set({ error: getErrorMessage(err, 'Failed to create reminder.') });
      return false;
    }
  },

  dismissReminder: async (id) => {
    try {
      await remindersApi.dismiss(id);
      get().fetchReminders();
    } catch (err) {
      console.error('Failed to dismiss reminder', err);
    }
  },

  // Notifications Actions
  fetchNotifications: async () => {
    try {
      const response = await notificationsApi.list();
      const items = (response.data || []) as NotificationItem[];
      set({ notifications: items });
      syncInAppNotificationsToNativeStatusBar(items);
    } catch (err) {
      console.error('Failed to fetch notifications', err);
    }
  },

  fetchUnreadCount: async () => {
    try {
      const response = await notificationsApi.getUnreadCount();
      set({ unreadNotificationCount: (response.data.count as number) || 0 });
    } catch (err) {
      console.error('Failed to fetch unread count', err);
    }
  },

  markNotificationRead: async (id) => {
    try {
      await notificationsApi.markAsRead(id);
      get().fetchNotifications();
      get().fetchUnreadCount();
    } catch (err) {
      console.error('Failed to mark notification as read', err);
    }
  },

  fetchNightBrief: async () => {
    try {
      const response = await notificationsApi.getNightBrief();
      set({ nightBrief: (response.data as NightBrief) || null });
    } catch (err) {
      console.error('Failed to fetch night brief', err);
    }
  },

  // AI Conversation
  fetchAIHistory: async () => {
    set({ aiHistoryLoading: true, aiChatError: null });
    try {
      const data = await aiApi.history(200);
      set({ aiMessages: data.messages ?? [], aiHistoryLoading: false });
    } catch (err) {
      console.error('Failed to load AI history', err);
      set({
        aiMessages: [],
        aiHistoryLoading: false,
        aiChatError: 'Could not load your conversation. Please try again.',
      });
    }
  },

  sendAIMessage: async (text) => {
    const trimmed = text.trim();
    if (!trimmed) return;

    const now = new Date().toISOString();
    const tempId = `temp-${now}`;
    const userMsg: ChatMessage = {
      id: tempId,
      role: 'user',
      content: trimmed,
      day: now,
      created_at: now,
    };

    set((s) => ({
      aiSending: true,
      aiChatError: null,
      aiMessages: [...s.aiMessages, userMsg],
    }));

    try {
      const reply = await aiApi.chat(trimmed);
      set((s) => ({ aiMessages: [...s.aiMessages, reply] }));
    } catch (err) {
      console.error('AI chat request failed', err);
      set((s) => ({
        aiMessages: s.aiMessages.filter((m) => m.id !== tempId),
        aiChatError: getErrorMessage(err, 'Could not reach Knowtis AI. Please try again.'),
      }));
    } finally {
      set({ aiSending: false });
    }
  },

  // Clears the whole chat server-side, resets local messages, and bumps a
  // signal timestamp so any mounted AI page can refetch (now empty) history.
  clearAIChat: async () => {
    set({ aiClearing: true, aiChatError: null });
    try {
      await aiApi.clear();
      set({ aiMessages: [], aiClearing: false });
      return true;
    } catch (err: unknown) {
      set({
        aiClearing: false,
        aiChatError: getErrorMessage(err, 'Failed to clear AI chat.'),
      });
      return false;
    }
  },

  updateProfile: async (data) => {
    set({ loading: true, error: null });
    try {
      const response = await authApi.updateProfile(data);
      const normalizedUser = normalizeUser(response.data as Record<string, unknown>);
      await setPersistentItem('knowtis_user', JSON.stringify(normalizedUser));
      set({
        user: normalizedUser,
        loading: false,
      });
      return true;
    } catch (err: unknown) {
      set({
        loading: false,
        error: getErrorMessage(err, 'Failed to update profile.'),
      });
      return false;
    }
  },

  deleteAccount: async () => {
    set({ loading: true, error: null });
    try {
      await authApi.deleteAccount();
      get().logout();
      set({ loading: false });
      return true;
    } catch (err: unknown) {
      set({
        loading: false,
        error: getErrorMessage(err, 'Failed to delete account.'),
      });
      return false;
    }
  },

  upgradeToPremium: async (tier) => {
    set({ loading: true, error: null });
    try {
      const response = await authApi.upgradeToPremium({ tier });
      set({
        user: normalizeUser(response.data as Record<string, unknown>),
        loading: false,
      });
      return true;
    } catch (err: unknown) {
      set({
        loading: false,
        error: getErrorMessage(err, 'Failed to upgrade subscription.'),
      });
      return false;
    }
  },

  fetchWidgetData: async () => {
    try {
      const response = await widgetApi.getAndroidWidgetData();
      set({ widgetData: response });
    } catch (err) {
      console.error('Failed to fetch widget data', err);
    }
  },

  fetchActiveSubscription: async () => {
    try {
      const response = await billingApi.getSubscription();
      set({ activeSubscription: response });
    } catch (err) {
      console.error('Failed to fetch active subscription', err);
    }
  },
}));

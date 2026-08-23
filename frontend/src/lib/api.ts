/*
API Client - Axios Service for Knowtis Backend
*/
import axios from 'axios';
import { getPersistentItemSync, getPersistentItem, setPersistentItem, removePersistentItem } from './persistent-storage';

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  (process.env.NEXT_PUBLIC_API_URL ? `${process.env.NEXT_PUBLIC_API_URL}/api/v1` : '') ||
  'http://localhost:8000/api/v1';

/** Full OAuth start URL for the Google sign-in button. */
export const GOOGLE_OAUTH_URL = `${API_BASE_URL}/auth/google`;

type JsonRecord = Record<string, unknown>;

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  // Global request timeout — 12s is generous enough for slow LLM-backed
  // endpoints (AI catch-up, OCR) but stops requests from hanging forever
  // when the backend is unreachable and blocking the splash screen.
  timeout: 12000,
});

// Automatically inject JWT token in the Authorization header.
apiClient.interceptors.request.use(
  async (config) => {
    if (typeof window !== 'undefined') {
      let token = getPersistentItemSync('knowtis_token');
      if (!token) {
        token = await getPersistentItem('knowtis_token');
      }
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor: automatically attempt silent refresh on HTTP 401 Unauthorized
let isRefreshingToken = false;
let failedQueue: Array<{ resolve: (token: string) => void; reject: (err: unknown) => void }> = [];

const processQueue = (error: unknown, token: string | null = null) => {
  failedQueue.forEach((prom) => {
    if (error) {
      prom.reject(error);
    } else if (token) {
      prom.resolve(token);
    }
  });
  failedQueue = [];
};

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    if (
      error.response?.status === 401 &&
      originalRequest &&
      !originalRequest._retry &&
      !originalRequest.url?.includes('/auth/login') &&
      !originalRequest.url?.includes('/auth/refresh')
    ) {
      if (isRefreshingToken) {
        return new Promise((resolve, reject) => {
          failedQueue.push({
            resolve: (token: string) => {
              originalRequest.headers.Authorization = `Bearer ${token}`;
              resolve(apiClient(originalRequest));
            },
            reject: (err: unknown) => {
              reject(err);
            },
          });
        });
      }

      originalRequest._retry = true;
      isRefreshingToken = true;

      const refreshToken = await getPersistentItem('knowtis_refresh_token');
      if (refreshToken) {
        try {
          const { data } = await axios.post(`${API_BASE_URL}/auth/refresh`, {
            refresh_token: refreshToken,
          });
          const newAccessToken = data.access_token;
          const newRefreshToken = data.refresh_token;

          await setPersistentItem('knowtis_token', newAccessToken);
          if (newRefreshToken) {
            await setPersistentItem('knowtis_refresh_token', newRefreshToken);
          }

          apiClient.defaults.headers.common.Authorization = `Bearer ${newAccessToken}`;
          originalRequest.headers.Authorization = `Bearer ${newAccessToken}`;

          processQueue(null, newAccessToken);
          return apiClient(originalRequest);
        } catch (refreshError) {
          processQueue(refreshError, null);
          await removePersistentItem('knowtis_token');
          await removePersistentItem('knowtis_refresh_token');
          return Promise.reject(refreshError);
        } finally {
          isRefreshingToken = false;
        }
      }
    }
    return Promise.reject(error);
  }
);

// Auth Service Endpoints
export const authApi = {
  register: (data: JsonRecord) => apiClient.post('/auth/register', data),
  login: (data: JsonRecord) => apiClient.post('/auth/login', data),
  checkUsername: (username: string) =>
    apiClient.get('/auth/check-username', { params: { username } }),
  getCurrentUser: () => apiClient.get('/auth/me'),
  updateProfile: (data: JsonRecord) => apiClient.put('/auth/profile', data),
  deleteAccount: () => apiClient.delete('/auth/profile'),
  upgradeToPremium: (data: { tier: string }) => apiClient.put('/auth/upgrade', data),
};

// Academic Events Endpoints
export const eventsApi = {
  list: (params?: { skip?: number; limit?: number; event_type?: string; course_code?: string }) => 
    apiClient.get('/events', { params }),
  get: (id: string) => apiClient.get(`/events/${id}`),
  create: (data: JsonRecord) => apiClient.post('/events', data),
  update: (id: string, data: JsonRecord) => apiClient.put(`/events/${id}`, data),
  delete: (id: string) => apiClient.delete(`/events/${id}`),
};

// Training & Prediction Feedback Endpoints
export const trainingApi = {
  getPredictions: (params?: { skip?: number; limit?: number; needs_review?: boolean }) =>
    apiClient.get('/training/predictions', { params }),
  submitFeedback: (data: {
    prediction_id?: string;
    academic_event_id?: string;
    feedback_type: 'confirmed_correct' | 'corrected' | 'reported_noise';
    corrected_category?: string;
    corrected_course_code?: string;
    corrected_date_time?: string;
    corrected_event_type?: string;
    notes?: string;
  }) => apiClient.post('/training/feedback', data),
};

// Reminders Endpoints
export const remindersApi = {
  list: (params?: { active_only?: boolean; limit?: number }) => 
    apiClient.get('/reminders', { params }),
  create: (data: { event_id: string; reminder_type?: string; delivery_channel?: string; days_before?: number }) => 
    apiClient.post('/reminders', data),
  dismiss: (id: string) => apiClient.delete(`/reminders/${id}`),
};

// WhatsApp Integration Endpoints
export const whatsappApi = {
  join: (data: { invite_link: string }) => apiClient.post('/whatsapp/join', data),
  list: () => apiClient.get('/whatsapp'),
  unlink: (id: string) => apiClient.delete(`/whatsapp/${id}`),
  getStatus: (id: string) => apiClient.get(`/whatsapp/${id}/status`),
  updateFilters: (id: string, data: { monitored_keywords?: string[]; monitored_courses?: string[]; filter_mode?: string }) =>
    apiClient.patch(`/whatsapp/${id}/filters`, data),
};

// Notifications Inbox Endpoints
export const notificationsApi = {
  list: () => apiClient.get('/notifications'),
  getUnreadCount: () => apiClient.get('/notifications/count'),
  markAsRead: (id: string) => apiClient.post(`/notifications/${id}/read`),
  getNightBrief: () => apiClient.get('/notifications/brief/night'),
};

// AI Conversation Endpoints
export type ChatRole = 'user' | 'assistant' | 'brief';

export interface ActionConfirmation {
  tool: string;
  success: boolean;
  message: string;
}

export interface ChatMessage {
  id: string;
  role: ChatRole;
  content: string;
  day: string;
  created_at: string;
  actions?: ActionConfirmation[];
}

export interface ChatHistoryResponse {
  messages: ChatMessage[];
  grouped_by_day: boolean;
}

export interface ChatClearResponse {
  deleted: number;
}

export const aiApi = {
  chat: (message: string) =>
    apiClient.post<ChatMessage>('/ai/chat', { message }).then((res) => res.data),
  history: (limit = 200) =>
    apiClient
      .get<ChatHistoryResponse>('/ai/chat/history', { params: { limit } })
      .then((res) => res.data),
  clear: () =>
    apiClient.delete<ChatClearResponse>('/ai/chat').then((res) => res.data),
};

// Widget Endpoints
export const widgetApi = {
  getAndroidWidgetData: () => apiClient.get('/widgets/android').then((res) => res.data),
};

// Billing Endpoints
export const billingApi = {
  getSubscription: () => apiClient.get('/billing/subscription').then((res) => res.data),
};

// Onboarding / Research Endpoints
export const onboardingApi = {
  getResearch: () => apiClient.get('/onboarding/research').then((res) => res.data),
  saveResearch: (data: { heard_about: string; primary_use_case: string; skipped: boolean; other_text?: string | null }) =>
    apiClient.post('/onboarding/research', data).then((res) => res.data),
};

// Admin Endpoints
export const adminApi = {
  getStats: () => apiClient.get('/admin/stats').then((res) => res.data),
  getUsers: (params?: { search?: string; role?: string; tier?: string; is_active?: boolean; skip?: number; limit?: number }) =>
    apiClient.get('/admin/users', { params }).then((res) => res.data),
  getUserDetails: (userId: string) => apiClient.get(`/admin/users/${userId}`).then((res) => res.data),
  updateUserStatus: (userId: string, data: { is_active?: boolean; role?: string; tier?: string; ai_tokens_received?: number }) =>
    apiClient.put(`/admin/users/${userId}/status`, data).then((res) => res.data),
  getWhatsAppGroups: (params?: { coverage_state?: string; search?: string; skip?: number; limit?: number }) =>
    apiClient.get('/admin/whatsapp-groups', { params }).then((res) => res.data),
  overrideGroupState: (groupId: string, data: { coverage_state: string }) =>
    apiClient.post(`/admin/whatsapp-groups/${groupId}/override-state`, data).then((res) => res.data),
  getSystemHealth: () => apiClient.get('/admin/system/health').then((res) => res.data),
  getAiPredictions: (params?: { skip?: number; limit?: number; needs_review?: boolean }) =>
    apiClient.get('/admin/ai/predictions', { params }).then((res) => res.data),
  sendBroadcast: (data: { title: string; description: string; target_tier: string }) =>
    apiClient.post('/admin/broadcast', data).then((res) => res.data),
  // Notification Templates
  getNotificationTemplates: (params?: { search?: string; category?: string; is_active?: boolean; skip?: number; limit?: number }) =>
    apiClient.get('/admin/notification-templates', { params }).then((res) => res.data),
  getNotificationTemplate: (templateId: string) => apiClient.get(`/admin/notification-templates/${templateId}`).then((res) => res.data),
  createNotificationTemplate: (data: any) => apiClient.post('/admin/notification-templates', data).then((res) => res.data),
  updateNotificationTemplate: (templateId: string, data: any) => apiClient.put(`/admin/notification-templates/${templateId}`, data).then((res) => res.data),
  deleteNotificationTemplate: (templateId: string) => apiClient.delete(`/admin/notification-templates/${templateId}`).then((res) => res.data),
  testNotificationTemplate: (templateId: string, variables: any) => apiClient.post(`/admin/notification-templates/${templateId}/test`, variables).then((res) => res.data),
  // Rate Limit Dashboard
  getRateLimitLogs: (params?: { user_id?: string; ip_address?: string; endpoint?: string; blocked_only?: boolean; skip?: number; limit?: number }) =>
    apiClient.get('/admin/rate-limit/logs', { params }).then((res) => res.data),
  getRateLimitStats: (params?: { hours?: number }) => apiClient.get('/admin/rate-limit/stats', { params }).then((res) => res.data),
  clearRateLimitLogs: (older_than_days?: number) => apiClient.delete('/admin/rate-limit/logs', { params: { older_than_days } }).then((res) => res.data),
  // WhatsApp Connector & QR Code
  getConnectorStatus: () => apiClient.get('/admin/whatsapp/connector-status').then((res) => res.data),
  generateQr: () => apiClient.post('/admin/whatsapp/generate-qr').then((res) => res.data),
  resetConnectorSession: () => apiClient.post('/admin/whatsapp/reset').then((res) => res.data),
  disconnectConnector: () => apiClient.post('/admin/whatsapp/disconnect').then((res) => res.data),
};

export function openAdminDashboard() {
  if (typeof window === 'undefined') return;

  const isNative = typeof (window as any).Capacitor !== 'undefined' ? (window as any).Capacitor.isNativePlatform?.() : false;
  const isLocalhost = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1' || window.location.protocol === 'capacitor:';

  let adminUrl: string;
  if (isNative) {
    // Native app: admin dashboard is served by the frontend
    adminUrl = `${window.location.origin}/admin/index.html`;
  } else if (isLocalhost) {
    // Localhost: admin dashboard is served by the frontend on port 3000
    adminUrl = `${window.location.origin}/admin/index.html`;
  } else {
    // Production: admin dashboard is served by the frontend
    adminUrl = `${window.location.origin}/admin/index.html`;
  }

  // Launch external system browser
  if (isNative) {
    try {
      const a = document.createElement('a');
      a.href = adminUrl;
      a.target = '_system';
      a.rel = 'noopener noreferrer';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    } catch {
      window.open(adminUrl, '_system') || window.open(adminUrl, '_blank');
    }
  } else {
    window.open(adminUrl, '_blank');
  }
}

export default apiClient;

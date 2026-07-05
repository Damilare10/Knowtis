/*
API Client - Axios Service for Knowtis Backend
*/
import axios from 'axios';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000/api/v1';

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
// The backend (get_current_user) accepts a Bearer header, so a query
// param is not needed and would otherwise pollute filtered GET requests.
apiClient.interceptors.request.use(
  (config) => {
    if (typeof window !== 'undefined') {
      const token = localStorage.getItem('knowtis_token');
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }
    }
    return config;
  },
  (error) => Promise.reject(error)
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
  delete: (id: string) => apiClient.delete(`/events/${id}`),
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

export interface ChatMessage {
  id: string;
  role: ChatRole;
  content: string;
  day: string;
  created_at: string;
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

export default apiClient;

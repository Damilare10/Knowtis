# Knowtis Project Rules & AI Agent Instructions

## 1. Project Primary Architecture Target: Android / Mobile Application
- **PRIMARY TARGET**: Knowtis is **primarily a native Android (and iOS) mobile application** built using Next.js / React compiled with **Capacitor**.
- **SECONDARY TARGET**: The web version served via Nginx on the VPS is a secondary preview and marketing endpoint.

---

## 2. Platform-Specific Implementation Directives

### A. Notifications (CRITICAL)
- **DO NOT USE Web Browser Notification APIs** (e.g., `Notification.requestPermission()`, `new Notification()`, Web Push Service Workers).
- **ALWAYS USE Capacitor Mobile Notification APIs**:
  - Use `@capacitor/push-notifications` for Firebase Cloud Messaging (FCM) push notifications.
  - Use `@capacitor/local-notifications` for scheduled local alarms, reminders, and academic deadline alerts.
  - Configure native Android Notification Channels (`PushNotifications.createChannel()`) for urgent academic alerts.

### B. Mobile Native Features & Plugins
- Use `@capacitor/preferences` for local device storage (auth tokens, onboarding status, user preferences).
- Use `@capacitor/app` for Android back-button navigation handling and lifecycle events (`appStateChange`).
- Use `@capacitor/device` and `@capacitor/status-bar` for native Android status bar styling and safe area insets.
- Always check `Capacitor.isNativePlatform()` before executing native device features.

### C. UX, Mobile Layout & Touch Design
- **Safe Area Insets**: Always include safe area top/bottom padding (`padding-top: max(16px, env(safe-area-inset-top))`, `pb-nav` for mobile bottom navigation).
- **Touch Targets**: Ensure buttons, list items, and interactive elements have minimum 48px × 48px touch targets for Android mobile screens.
- **Mobile Navigation**: Maintain the floating bottom navigation bar (`BottomNav`) and mobile-friendly gesture flows for Android phone viewports.

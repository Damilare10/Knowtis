'use client';

import React, { useEffect } from 'react';
import { motion } from 'framer-motion';
import { Bell, Check } from 'lucide-react';
import { useAppStore } from '@/lib/store';
import { TYPE_META, TYPE_COLOR, relativeDay } from '@/lib/events';

const EASE = [0.16, 1, 0.3, 1] as const;
const FADE = (i = 0) => ({
  initial: { opacity: 0, y: 18 },
  animate: { opacity: 1, y: 0 },
  transition: { delay: i * 0.07, duration: 0.55, ease: EASE },
});

function timeAgo(iso?: string): string {
  if (!iso) return '';
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'Just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return relativeDay(iso);
}

export default function NotificationsPage() {
  const { notifications, unreadNotificationCount, fetchNotifications, markNotificationRead, fetchUnreadCount } = useAppStore();

  useEffect(() => {
    fetchNotifications();
    fetchUnreadCount();
  }, [fetchNotifications, fetchUnreadCount]);

  return (
    <div className="app-page">
      <motion.div {...FADE(0)} className="mb-4">
        <h1 className="page-title">Your <span className="orange-highlight">alerts</span></h1>
        <p className="page-copy mt-2">Important academic updates surfaced from your class chats.</p>
        {unreadNotificationCount > 0 && (
          <span className="badge badge-danger mt-3">{unreadNotificationCount} new</span>
        )}
      </motion.div>

      {notifications.length === 0 ? (
        <motion.div {...FADE(1)}>
          <div className="clay-card p-6 flex flex-col items-center justify-center text-center py-16">
            <div className="w-16 h-16 rounded-[20px] clay-icon bg-[#F4F3EF] flex items-center justify-center mb-4">
              <Bell className="w-7 h-7 text-[var(--text-3)]" />
            </div>
            <p className="font-black text-sm tracking-[-0.01em] text-[var(--text-1)]">No notifications yet</p>
            <p className="body-sm text-[var(--text-3)] mt-1">Important updates will appear here.</p>
          </div>
        </motion.div>
      ) : (
        <motion.div {...FADE(1)} className="grid grid-cols-1 lg:grid-cols-2 gap-3">
          {notifications.map((notification, i) => {
            const eventType = notification.event?.event_type;
            const meta = eventType ? TYPE_META[eventType] : null;
            const color = eventType ? TYPE_COLOR[eventType] : 'var(--primary)';
            const Icon = meta?.icon ?? Bell;
            return (
              <motion.article
                key={notification.id}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.05 + i * 0.05, ease: EASE }}
                className={`group flex items-start gap-3.5 rounded-[24px] border border-transparent p-4 transition-all hover:-translate-y-0.5 ${
                  !notification.is_read
                    ? 'bg-white/60 shadow-[0_18px_40px_rgba(0,0,0,0.04),inset_0_1px_0_rgba(255,255,255,1)] backdrop-blur-md'
                    : 'bg-white/40 border-[var(--border-soft)]'
                }`}
              >
                <div className="w-11 h-11 rounded-[18px] clay-icon flex items-center justify-center shrink-0" style={{ background: color + '18' }}>
                  <Icon className="w-5 h-5" style={{ color }} />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-start justify-between gap-3 mb-1">
                    <p className="text-sm font-black tracking-[-0.01em] text-[var(--text-1)]">{notification.title}</p>
                    {!notification.is_read && (
                      <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-[var(--danger)] animate-pulse" />
                    )}
                  </div>
                  <p className="text-xs font-semibold text-[var(--text-3)] leading-relaxed">{notification.description}</p>
                  <div className="flex items-center justify-between gap-2 mt-2">
                    <span className="text-[11px] font-bold tabular-nums text-[var(--text-3)]">{timeAgo(notification.created_at)}</span>
                    {!notification.is_read && (
                      <button
                        onClick={() => markNotificationRead(notification.id)}
                        className="inline-flex items-center gap-1.5 text-xs font-black text-[var(--primary)] transition-colors hover:text-[#C83C21]"
                      >
                        <Check className="h-3.5 w-3.5" />
                        Mark read
                      </button>
                    )}
                  </div>
                </div>
              </motion.article>
            );
          })}
        </motion.div>
      )}
    </div>
  );
}

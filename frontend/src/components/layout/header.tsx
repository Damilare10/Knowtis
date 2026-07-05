'use client';
import React, { useState, useEffect, useRef } from 'react';
import { Bell, Check, CircleAlert, WifiOff } from 'lucide-react';
import { motion } from 'framer-motion';
import { useAppStore } from '@/lib/store';
import { usePathname } from 'next/navigation';

const PAGE_TITLES: Record<string, string> = {
  '/dashboard': 'Home',
  '/updates':   'Updates',
  '/calendar':  'Calendar',
  '/ai':        'AI Assistant',
  '/profile':   'Profile',
  '/groups':    'Groups',
  '/events':    'Events',
  '/reminders': 'Reminders',
  '/notifications': 'Alerts',
};

export default function Header() {
  const pathname = usePathname();
  const { unreadNotificationCount, notifications, fetchNotifications, markNotificationRead, fetchUnreadCount, groups } = useAppStore();
  const [notifOpen, setNotifOpen] = useState(false);
  const dropRef = useRef<HTMLDivElement>(null);

  const title = Object.entries(PAGE_TITLES).find(([k]) => pathname.startsWith(k))?.[1] ?? 'Knowtis';
  const connected = groups.filter(g => g.coverage_state === 'ACTIVE').length;
  const isDegraded = groups.some(g => ['DEGRADED', 'PAUSED', 'RECOVERING'].includes(g.coverage_state));

  useEffect(() => {
    fetchUnreadCount();
    const handler = (e: MouseEvent) => {
      if (dropRef.current && !dropRef.current.contains(e.target as Node)) setNotifOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [fetchUnreadCount]);

  const openNotif = () => {
    setNotifOpen(v => !v);
    if (!notifOpen) fetchNotifications();
  };

  return (
    <header className="h-[68px] sticky top-0 z-30 mx-3 mt-3 rounded-[30px] border border-[var(--border-soft)] bg-white shadow-[0_18px_42px_rgba(30,30,30,0.08),inset_0_10px_18px_rgba(255,255,255,0.70)] flex items-center justify-between px-5">
      {/* Left: page title */}
      <div className="flex items-center gap-3">
        <h1 className="text-lg font-black lowercase text-[var(--text-1)] tracking-[-0.055em]">{title}</h1>
      </div>

      {/* Right */}
      <div className="flex items-center gap-2">
        {/* Connection status chip */}
        {groups.length > 0 && (
          <div className={`hidden sm:flex items-center gap-1.5 px-3.5 py-2 rounded-full text-xs font-extrabold border shadow-[inset_0_5px_9px_rgba(255,255,255,0.55)] ${
            isDegraded ? 'bg-[var(--warning-dim)] text-[#A66512] border-[#F8E1AF]' : 'bg-[var(--success-dim)] text-[#14794F] border-[#CFEFDD]'
          }`}>
            <div className={`w-1.5 h-1.5 rounded-full animate-dot ${isDegraded ? 'bg-[var(--warning)]' : 'bg-[var(--success)]'}`} />
            {isDegraded ? 'Degraded' : `Monitoring ${connected}`}
          </div>
        )}

        {/* No groups */}
        {groups.length === 0 && (
          <div className="hidden sm:flex items-center gap-1.5 px-3.5 py-2 rounded-full bg-[#FBFBFA] border border-[var(--border)] text-xs font-extrabold text-[var(--text-3)]">
            <WifiOff className="w-3 h-3" />
            No groups
          </div>
        )}

        {/* Notification bell */}
        <div className="relative" ref={dropRef}>
          <motion.button
            whileHover={{ scale: 1.06, backgroundColor: '#ffffff' }}
            whileTap={{ scale: 0.93 }}
            transition={{ type: 'spring', stiffness: 400, damping: 18 }}
            onClick={openNotif}
            className="w-10 h-10 flex items-center justify-center rounded-[18px] bg-[#FBFBFA] border border-[var(--border)] shadow-[inset_0_5px_9px_rgba(255,255,255,0.70)] relative text-[var(--text-2)]"
            aria-label="Notifications"
          >
            <Bell className="w-[18px] h-[18px]" />
            {unreadNotificationCount > 0 && (
              <span className="absolute top-1.5 right-1.5 w-2 h-2 rounded-full bg-[var(--danger)]" />
            )}
          </motion.button>

          {notifOpen && (
            <div className="absolute right-0 mt-3 w-[310px] clay-card-strong z-50 overflow-hidden">
              <div className="p-4 border-b border-[var(--border-soft)] flex items-center justify-between">
                <span className="heading-sm text-[var(--text-1)]">Notifications</span>
                {unreadNotificationCount > 0 && (
                  <span className="badge badge-danger">{unreadNotificationCount} new</span>
                )}
              </div>
              <div className="max-h-64 overflow-y-auto">
                {notifications.length === 0 ? (
                  <div className="p-8 text-center">
                    <Bell className="w-8 h-8 text-[var(--text-3)] mx-auto mb-2" />
                    <p className="text-xs text-[var(--text-3)] font-medium">No notifications yet</p>
                  </div>
                ) : (
                  notifications.map(n => (
                    <div key={n.id} className={`p-4 flex gap-3 border-b border-[var(--border-soft)] last:border-0 hover:bg-[#FBFBFA] transition-colors ${!n.is_read ? 'bg-[var(--primary-dim)]' : ''}`}>
                      <CircleAlert className="w-4 h-4 text-[var(--primary)] mt-0.5 shrink-0" />
                      <div className="flex-1 min-w-0">
                        <p className="text-xs font-bold text-[var(--text-1)] truncate">{n.title}</p>
                        <p className="text-[11px] text-[var(--text-3)] mt-0.5 leading-relaxed line-clamp-2">{n.description}</p>
                        {!n.is_read && (
                          <button onClick={() => markNotificationRead(n.id)} className="mt-1.5 text-[10px] font-black text-[var(--primary)] flex items-center gap-1">
                            <Check className="w-3 h-3" /> Mark read
                          </button>
                        )}
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}

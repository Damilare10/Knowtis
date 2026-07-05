/*
Reminders Management Component - Modernized
*/
'use client';

import React, { useEffect } from 'react';
import { useAppStore } from '@/lib/store';
import { 
  Clock, 
  Trash2, 
  Bell, 
  CalendarDays,
  CheckCircle2
} from 'lucide-react';
import { motion } from 'framer-motion';

export default function RemindersPage() {
  const { reminders, fetchReminders, fetchEvents, dismissReminder } = useAppStore();

  useEffect(() => {
    let active = true;
    // Events must load first so reminders can hydrate their nested `event`.
    (async () => {
      await fetchEvents({ limit: 100 });
      if (active) fetchReminders();
    })();
    return () => { active = false; };
  }, [fetchReminders, fetchEvents]);

  return (
    <div className="app-page max-w-5xl">
      <motion.div 
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <h1 className="page-title">
          Academic <span className="orange-highlight">reminders</span>
        </h1>
        <p className="page-copy mt-2">
          Review and cancel your automated deadline alerts and notification times.
        </p>
      </motion.div>

      {reminders.length === 0 ? (
        <motion.div 
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="clay-card p-6 flex flex-col items-center justify-center text-center py-16"
        >
          <div className="w-16 h-16 rounded-[20px] clay-icon bg-[#F4F3EF] flex items-center justify-center mb-4">
            <Clock className="w-7 h-7 text-[var(--text-3)]" />
          </div>
          <p className="font-black text-sm tracking-[-0.01em] text-[var(--text-1)]">No reminders scheduled yet</p>
          <p className="body-sm text-[var(--text-3)] mt-1">Add reminders to deadlines inside the Events page.</p>
        </motion.div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {reminders.map((reminder, index) => (
            <motion.div 
              key={reminder.id}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.04 }}
              className="clay-card p-5 flex flex-col justify-between hover:-translate-y-0.5 transition-all duration-200"
            >
              <div className="space-y-3">
                <div className="flex justify-between items-start gap-2">
                  <span className="badge badge-primary">
                    {reminder.delivery_channel}
                  </span>

                  {reminder.is_sent ? (
                    <span className="text-[10px] font-bold text-[var(--success)] flex items-center gap-1">
                      <CheckCircle2 className="w-3.5 h-3.5" /> Sent
                    </span>
                  ) : (
                    <span className="text-[10px] font-bold text-[var(--primary)] flex items-center gap-1 animate-pulse">
                      <Bell className="w-3.5 h-3.5" /> Pending
                    </span>
                  )}
                </div>

                <h3 className="font-black text-sm tracking-[-0.01em] text-[var(--text-1)] line-clamp-1">
                  {reminder.event?.title || 'Academic reminder'}
                </h3>

                {reminder.event?.description ? (
                  <p className="text-xs text-[var(--text-3)] line-clamp-2 leading-relaxed font-medium">
                    {reminder.event.description}
                  </p>
                ) : (
                  <p className="text-xs text-[var(--text-3)] leading-relaxed font-medium">
                    {reminder.event?.course_code ? `${reminder.event.course_code} · ` : ''}Linked academic event.
                  </p>
                )}
              </div>

              <div className="flex justify-between items-center pt-4 mt-5 border-t border-[var(--border-soft)]">
                <div className="flex items-center gap-2 text-xs text-[var(--text-3)] font-semibold">
                  <CalendarDays className="w-4 h-4 text-[var(--text-3)]" />
                  <span>
                    {reminder.scheduled_time
                      ? `Alert: ${new Date(reminder.scheduled_time).toLocaleDateString('en-US', { timeZone: 'Africa/Lagos', month: 'short', day: 'numeric' })} at ${new Date(reminder.scheduled_time).toLocaleTimeString('en-US', { timeZone: 'Africa/Lagos', hour: '2-digit', minute: '2-digit', hour12: false })}`
                      : 'Not scheduled'}
                  </span>
                </div>
                
                <button
                  onClick={() => {
                    if (confirm("Are you sure you want to dismiss this reminder?")) {
                      dismissReminder(reminder.id);
                    }
                  }}
                  className="p-2 rounded-[14px] text-[var(--text-3)] hover:bg-[var(--danger-dim)] hover:text-[var(--danger)] transition-colors cursor-pointer"
                  title="Dismiss Reminder"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>

            </motion.div>
          ))}
        </div>
      )}
    </div>
  );
}

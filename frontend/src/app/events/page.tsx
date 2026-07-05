'use client';
import React, { useState, useEffect } from 'react';
import { useAppStore } from '@/lib/store';
import type { EventType } from '@/lib/events';
import { TYPE_STYLE } from '@/lib/events';
import { Search, Clock, AlertTriangle, MapPin, Calendar, Check, Trash2 } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

const TYPES: EventType[] = ['DEADLINE', 'ALERT', 'EVENT', 'INFO'];

export default function EventsPage() {
  const { events, fetchEvents, deleteEvent, createReminder, reminders, fetchReminders } = useAppStore();
  const [eventType, setEventType] = useState<'ALL' | EventType>('ALL');
  const [query, setQuery] = useState('');
  const [debouncedQuery, setDebouncedQuery] = useState('');
  const [toast, setToast] = useState<string | null>(null);

  // Debounce search to avoid a request per keystroke.
  useEffect(() => {
    const t = setTimeout(() => setDebouncedQuery(query), 300);
    return () => clearTimeout(t);
  }, [query]);

  // Reminders don't depend on the search query — fetch once on mount.
  useEffect(() => { fetchReminders(); }, [fetchReminders]);

  useEffect(() => {
    fetchEvents({
      event_type: eventType === 'ALL' ? undefined : eventType,
      course_code: debouncedQuery || undefined,
      limit: 50,
    });
  }, [fetchEvents, eventType, debouncedQuery]);

  const hasReminder = (id: string) => reminders.some(r => r.event_id === id);

  const scheduleReminder = async (id: string, title: string) => {
    const ok = await createReminder(id, 1);
    if (ok) { setToast(`Reminder set for "${title}"`); setTimeout(() => setToast(null), 3000); }
  };

  const style = (type: EventType) => TYPE_STYLE[type];

  return (
    <div className="app-page">
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
        <h1 className="page-title">Manage <span className="orange-highlight">events</span></h1>
        <p className="page-copy mt-2">Set reminders and archive deadlines, alerts, and class events.</p>
      </motion.div>

      {/* Toast */}
      <AnimatePresence>
        {toast && (
          <motion.div
            initial={{ opacity: 0, y: 20, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, scale: 0.95 }}
            className="fixed bottom-24 left-1/2 -translate-x-1/2 z-50 flex items-center gap-2.5 px-5 py-3 rounded-full bg-white border border-[var(--border-soft)] text-[var(--text-1)] text-sm font-semibold shadow-[var(--shadow-3)]"
          >
            <Check className="w-4 h-4 text-[var(--success)]" />{toast}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Filters */}
      <div className="clay-card p-4 space-y-3">
        <div className="relative">
          <label htmlFor="event-search" className="sr-only">Search by course code</label>
          <Search className="absolute left-3.5 top-3.5 w-4 h-4 text-[var(--text-3)]" />
          <input
            id="event-search"
            type="text"
            autoComplete="off"
            placeholder="Search by course code..."
            value={query}
            onChange={e => setQuery(e.target.value)}
            className="input !pl-10"
          />
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => setEventType('ALL')}
            className={`px-4 py-1.5 rounded-full text-xs font-bold transition-all ${
              eventType === 'ALL' ? 'bg-[var(--text-1)] text-white' : 'bg-[#F4F3EF] text-[var(--text-2)] hover:bg-white'
            }`}
          >
            ALL
          </button>
          {TYPES.map(t => (
            <button
              key={t}
              onClick={() => setEventType(t)}
              className={`px-4 py-1.5 rounded-full text-xs font-bold transition-all ${
                eventType === t ? 'bg-[var(--text-1)] text-white' : 'bg-[#F4F3EF] text-[var(--text-2)] hover:bg-white'
              }`}
            >
              {t}
            </button>
          ))}
        </div>
      </div>

      {/* List */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        {events.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <div className="w-16 h-16 rounded-3xl bg-[#F4F3EF] flex items-center justify-center mb-4 clay-icon">
              <Calendar className="w-7 h-7 text-[var(--text-3)]" />
            </div>
            <p className="font-bold text-[var(--text-2)]">No events found</p>
            <p className="body-sm text-[var(--text-3)] mt-1">Try a different filter or link more groups</p>
          </div>
        ) : (
          events.map((event, i) => {
            const s = style(event.event_type);
            return (
              <motion.article
                key={event.id}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.04 }}
                className="clay-card p-4"
              >
                <div className="flex items-start gap-3">
                    <div className="w-10 h-10 clay-icon flex items-center justify-center shrink-0" style={{ background: s.bg }}>
                      {event.event_type === 'ALERT' ? (
                        <AlertTriangle className="w-[18px] h-[18px]" style={{ color: s.fg }} />
                      ) : event.event_type === 'DEADLINE' ? (
                        <Clock className="w-[18px] h-[18px]" style={{ color: s.fg }} />
                      ) : (
                        <Calendar className="w-[18px] h-[18px]" style={{ color: s.fg }} />
                      )}
                    </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex flex-wrap items-center gap-1.5 mb-1.5">
                      <span className="badge" style={{ background: s.bg, color: s.fg, borderColor: 'transparent' }}>{event.event_type}</span>
                      {event.course_code && <span className="badge badge-neutral">{event.course_code.toUpperCase()}</span>}
                      <span className="text-[10px] text-[var(--text-3)] font-bold tabular-nums">{Math.round(event.confidence_score * 100)}% confident</span>
                    </div>
                    <h3 className="text-sm font-black tracking-[-0.01em] text-[var(--text-1)] truncate">{event.title}</h3>
                    {event.description && (
                      <p className="body-sm text-[var(--text-2)] line-clamp-2 mt-1 leading-relaxed">{event.description}</p>
                    )}
                    {(event.date_time || event.venue) && (
                      <div className="flex flex-wrap gap-3 mt-2">
                        {event.date_time && (
                          <span className="flex items-center gap-1 text-xs text-[var(--text-3)] font-semibold">
                            <Clock className="w-3 h-3" />
                            {new Date(event.date_time).toLocaleDateString('en-US', { timeZone: 'Africa/Lagos', weekday: 'short', month: 'short', day: 'numeric' })}
                          </span>
                        )}
                        {event.venue && (
                          <span className="flex items-center gap-1 text-xs text-[var(--text-3)] font-semibold">
                            <MapPin className="w-3 h-3" />{event.venue}
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                </div>

                {/* Actions */}
                <div className="flex items-center gap-2 mt-3 pt-3 border-t border-[var(--border-soft)]">
                  {event.event_type === 'DEADLINE' && (
                    <button
                      disabled={hasReminder(event.id)}
                      onClick={() => scheduleReminder(event.id, event.title)}
                      className={`flex-1 flex items-center justify-center gap-1.5 py-2.5 rounded-[14px] text-xs font-black transition-all ${
                        hasReminder(event.id)
                          ? 'bg-[var(--success-dim)] text-[var(--success)] border border-[#A7F3D0]'
                          : 'bg-[var(--text-1)] text-white hover:bg-[#292929]'
                      }`}
                    >
                      {hasReminder(event.id) ? <><Check className="w-3.5 h-3.5" />Reminder Set</> : <><Clock className="w-3.5 h-3.5" />Set Reminder</>}
                    </button>
                  )}
                  <button
                    onClick={() => { if (confirm(`Archive "${event.title}"?`)) deleteEvent(event.id); }}
                    className="w-9 h-9 flex items-center justify-center rounded-[14px] border border-[var(--border)] text-[var(--text-3)] hover:bg-red-50 hover:text-[var(--danger)] hover:border-red-100 transition-all"
                    aria-label="Archive"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </motion.article>
            );
          })
        )}
      </div>
    </div>
  );
}

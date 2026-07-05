'use client';
import React, { useEffect, useMemo, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useAppStore } from '@/lib/store';
import type { AcademicEvent, EventType } from '@/lib/events';
import { TYPE_META, TYPE_STYLE, EVENT_TYPES, daysLeft, formatDateTime } from '@/lib/events';
import { BookOpen, Clock, ChevronRight, Sparkles, MapPin } from 'lucide-react';

type Filter = 'ALL' | EventType;
const FILTERS: Filter[] = ['ALL', ...EVENT_TYPES];

const FILTER_LABELS: Record<Filter, string> = {
  ALL: 'All',
  DEADLINE: 'Deadlines',
  ALERT: 'Alerts',
  EVENT: 'Events',
  INFO: 'Info',
};

export default function UpdatesPage() {
  const { events, fetchEvents } = useAppStore();
  const [active, setActive] = useState<Filter>('ALL');
  const [query, setQuery] = useState('');
  const [debouncedQuery, setDebouncedQuery] = useState('');

  // Debounce the search input so we don't fire a request per keystroke.
  useEffect(() => {
    const t = setTimeout(() => setDebouncedQuery(query), 300);
    return () => clearTimeout(t);
  }, [query]);

  useEffect(() => {
    fetchEvents({
      event_type: active === 'ALL' ? undefined : active,
      course_code: debouncedQuery || undefined,
      limit: 50,
    });
  }, [fetchEvents, active, debouncedQuery]);

  const filtered = useMemo(() => {
    const list = (events as AcademicEvent[])
      .filter((e) => active === 'ALL' || e.event_type === active)
      .filter((e) => !debouncedQuery || (e.course_code?.toLowerCase().includes(debouncedQuery.toLowerCase())) || e.title.toLowerCase().includes(debouncedQuery.toLowerCase()))
      .sort((a, b) => daysLeft(a.date_time) - daysLeft(b.date_time));
    return list;
  }, [events, active, debouncedQuery]);

  return (
    <div className="app-page">
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="mb-4">
        <h1 className="page-title">All class <span className="orange-highlight">updates</span></h1>
        <p className="page-copy mt-2">Deadlines, alerts, and class events in one place.</p>
      </motion.div>

      {/* Search + filter */}
      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.05 }}
        className="clay-card p-4 space-y-3 mb-2"
      >
        <div className="relative">
          <label htmlFor="update-search" className="sr-only">Search updates</label>
          <BookOpen className="absolute left-3.5 top-3.5 w-4 h-4 text-[var(--text-3)]" />
          <input
            id="update-search"
            type="text"
            autoComplete="off"
            placeholder="Search by course or title..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="input !pl-10"
          />
        </div>
        <div className="flex flex-wrap gap-2">
          {FILTERS.map((f) => {
            const count = f === 'ALL'
              ? (events as AcademicEvent[]).length
              : (events as AcademicEvent[]).filter((e) => e.event_type === f).length;
            return (
              <button
                key={f}
                onClick={() => setActive(f)}
                aria-pressed={active === f}
                className={`inline-flex items-center gap-1.5 rounded-full border px-4 py-1.5 text-xs font-bold transition-all ${
                  active === f
                    ? 'border-transparent bg-[var(--text-1)] text-white shadow-[0_8px_18px_rgba(23,23,23,0.18)]'
                    : 'border-[var(--border-soft)] bg-[#F4F3EF] text-[var(--text-2)] hover:border-[#E9E9E6] hover:bg-white'
                }`}
              >
                {FILTER_LABELS[f]}
                <span
                  className={`min-w-[18px] rounded-full px-1.5 text-[10px] font-black ${
                    active === f ? 'bg-white/15 text-white' : 'bg-white text-[var(--text-3)]'
                  }`}
                >
                  {count}
                </span>
              </button>
            );
          })}
        </div>
      </motion.div>

      {/* Cards */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        <AnimatePresence mode="popLayout">
          {filtered.map((u, i) => {
            const meta = TYPE_META[u.event_type];
            const s = TYPE_STYLE[u.event_type];
            const days = daysLeft(u.date_time);
            const isSmart = (u.confidence_score ?? 0) > 0 && u.urgency_score >= 0.6;
            return (
              <motion.article
                key={u.id}
                layout
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, scale: 0.97 }}
                transition={{ delay: i * 0.05, ease: [0.16, 1, 0.3, 1] }}
                className="clay-card p-4 cursor-pointer hover:-translate-y-0.5 transition-transform duration-200"
              >
                {/* Top row */}
                <div className="flex items-start gap-3">
                  <div className="w-10 h-10 clay-icon flex items-center justify-center shrink-0" style={{ background: s.bg }}>
                    <meta.icon className="w-[18px] h-[18px]" style={{ color: s.fg }} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex flex-wrap items-center gap-1.5 mb-1.5">
                      <span className="badge" style={{ background: s.bg, color: s.fg, borderColor: 'transparent' }}>{meta.tag}</span>
                      {u.course_code && (
                        <span className="badge badge-neutral">{u.course_code.toUpperCase()}</span>
                      )}
                      <span className="text-[10px] font-bold tabular-nums text-[var(--text-3)]">
                        {days <= 0 ? 'Due now' : `${days}d left`}
                      </span>
                    </div>
                    {/* AI label */}
                    {isSmart && (
                      <div className="flex items-center gap-1 mb-2">
                        <Sparkles className="w-3 h-3 text-[#FF5A36]" />
                        <span className="text-[10px] font-bold text-[#FF5A36] uppercase tracking-wider">Smart summary</span>
                      </div>
                    )}
                    <p className="text-sm font-black tracking-[-0.01em] text-[var(--text-1)]">{u.title}</p>
                    {u.description && (
                      <p className="body-sm text-[var(--text-2)] mt-1 leading-relaxed line-clamp-2">{u.description}</p>
                    )}
                    {(u.date_time || u.venue) && (
                      <div className="flex flex-wrap gap-3 mt-2">
                        {u.date_time && (
                          <span className="flex items-center gap-1 text-xs text-[var(--text-3)] font-semibold">
                            <Clock className="w-3 h-3" />{formatDateTime(u.date_time)}
                          </span>
                        )}
                        {u.venue && (
                          <span className="flex items-center gap-1 text-xs text-[var(--text-3)] font-semibold">
                            <MapPin className="w-3 h-3" />{u.venue}
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                </div>

                {/* Bottom row */}
                <div className="flex items-center justify-between mt-3 pt-3 border-t border-[var(--border-soft)]">
                  <span className="text-xs font-semibold text-[var(--text-3)]">
                    {new Date(u.created_at).toLocaleDateString([], { month: 'short', day: 'numeric' })}
                  </span>
                  <span className="flex items-center gap-0.5 text-xs font-bold text-[var(--primary)]">
                    Details <ChevronRight className="w-3.5 h-3.5" />
                  </span>
                </div>
              </motion.article>
            );
          })}
        </AnimatePresence>

        {filtered.length === 0 && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}
            className="flex flex-col items-center justify-center py-16 text-center"
          >
            <div className="w-16 h-16 rounded-3xl bg-[#F4F3EF] flex items-center justify-center mb-4 clay-icon">
              <BookOpen className="w-7 h-7 text-[var(--text-3)]" />
            </div>
            <p className="font-bold text-[var(--text-2)]">No updates found</p>
            <p className="body-sm text-[var(--text-3)] mt-1">Try a different filter or link more groups</p>
          </motion.div>
        )}
      </div>
    </div>
  );
}

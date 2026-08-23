'use client';
import React, { useEffect, useMemo, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useAppStore } from '@/lib/store';
import type { AcademicEvent, EventType } from '@/lib/events';
import { TYPE_META, TYPE_STYLE, EVENT_TYPES, daysLeft, formatDateTime, sortBySoonest } from '@/lib/events';
import { BookOpen, Clock, MapPin, ChevronDown, ArrowUpDown, Check, Circle, Trash2, X, AlertCircle, Sparkles } from 'lucide-react';
import EventDetailModal from '@/components/dashboard/event-detail-modal';
import Link from 'next/link';

type Filter = 'ALL' | EventType;
const FILTERS: Filter[] = ['ALL', ...EVENT_TYPES];

const FILTER_LABELS: Record<Filter, string> = {
  ALL: 'All',
  DEADLINE: 'Deadlines',
  ALERT: 'Alerts',
  EVENT: 'Events',
  INFO: 'Info',
};

type SortOrder = 'important' | 'newest' | 'oldest' | 'soonest';

const SORT_LABELS: Record<SortOrder, string> = {
  important: 'Most important',
  newest: 'Newest first',
  oldest: 'Oldest first',
  soonest: 'Soonest deadline',
};

const SORT_STORAGE_KEY = 'knowtis-updates-sort-order';

export default function UpdatesPage() {
  const { events, totalEvents, eventsTruncated, fetchEvents, confirmEvent, dismissEvent, deleteEvent } = useAppStore();
  const [active, setActive] = useState<Filter>('ALL');
  const [query, setQuery] = useState('');
  const [debouncedQuery, setDebouncedQuery] = useState('');
  const [filterOpen, setFilterOpen] = useState(false);
  const [sortOrder, setSortOrder] = useState<SortOrder>('important');
  const [sortOpen, setSortOpen] = useState(false);
  const [expandedPast, setExpandedPast] = useState<string | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [selectionMode, setSelectionMode] = useState(false);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const [selectedEvent, setSelectedEvent] = useState<AcademicEvent | null>(null);
  const longPressTimer = React.useRef<ReturnType<typeof setTimeout> | null>(null);
  const longPressTriggered = React.useRef(false);

  useEffect(() => {
    const savedSort = window.localStorage.getItem(SORT_STORAGE_KEY) as SortOrder | null;
    if (savedSort && savedSort in SORT_LABELS) setSortOrder(savedSort);
  }, []);

  const changeSortOrder = (nextSort: SortOrder) => {
    setSortOrder(nextSort);
    window.localStorage.setItem(SORT_STORAGE_KEY, nextSort);
  };

  const clearLongPress = () => {
    if (longPressTimer.current) clearTimeout(longPressTimer.current);
    longPressTimer.current = null;
  };

  const startLongPress = (id: string) => {
    clearLongPress();
    longPressTriggered.current = false;
    longPressTimer.current = setTimeout(() => {
      longPressTriggered.current = true;
      setSelectionMode(true);
      setSelectedIds((current) => new Set(current).add(id));
    }, 500);
  };

  const toggleSelected = (id: string) => {
    setSelectedIds((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      if (next.size === 0) setSelectionMode(false);
      return next;
    });
  };

  const cancelSelection = () => {
    setSelectedIds(new Set());
    setSelectionMode(false);
  };

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      const target = e.target as HTMLElement;
      if (!target.closest('[data-filter-dropdown]') && !target.closest('[data-sort-dropdown]')) {
        setFilterOpen(false);
        setSortOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  useEffect(() => {
    if (filterOpen) setSortOpen(false);
  }, [filterOpen]);

  useEffect(() => {
    if (sortOpen) setFilterOpen(false);
  }, [sortOpen]);

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
      .filter((e) => !debouncedQuery || (e.course_code?.toLowerCase().includes(debouncedQuery.toLowerCase())) || e.title.toLowerCase().includes(debouncedQuery.toLowerCase()));

    switch (sortOrder) {
      case 'newest':
        list.sort((a, b) => new Date(b.created_at || 0).getTime() - new Date(a.created_at || 0).getTime());
        break;
      case 'oldest':
        list.sort((a, b) => new Date(a.created_at || 0).getTime() - new Date(b.created_at || 0).getTime());
        break;
      case 'soonest':
        list.sort(sortBySoonest);
        break;
      case 'important':
      default:
        list.sort((a, b) => {
          const sa = (a.urgency_score * 0.5) + ((a.confidence_score ?? 0.8) * 0.3) + ((a.relevance_score ?? 0.7) * 0.2);
          const sb = (b.urgency_score * 0.5) + ((b.confidence_score ?? 0.8) * 0.3) + ((b.relevance_score ?? 0.7) * 0.2);
          return sb - sa;
        });
        break;
    }
    return list;
  }, [events, active, debouncedQuery, sortOrder]);

  const handleDeleteSelected = async () => {
    for (const id of selectedIds) {
      await deleteEvent(id);
    }
    setDeleteConfirmOpen(false);
    cancelSelection();
  };

  return (
    <div className="min-h-screen bg-[var(--bg-page)] pb-nav pt-4 px-4 max-w-5xl mx-auto space-y-4">
      <div className="flex items-center justify-between pt-2">
        <div>
          <h1 className="text-[28px] font-black tracking-[-0.04em] text-[var(--text-1)]">Updates</h1>
          <p className="text-xs font-semibold text-[var(--text-3)] mt-0.5">
            {totalEvents} {totalEvents === 1 ? 'announcement' : 'announcements'} tracked
          </p>
        </div>
      </div>

      {(eventsTruncated || totalEvents > events.length) && (
        <motion.div
          initial={{ opacity: 0, y: -6 }}
          animate={{ opacity: 1, y: 0 }}
          className="rounded-[20px] bg-gradient-to-r from-[#FFF0EB] to-[#FFF7ED] border border-[#FFD8CC] p-4 flex items-center justify-between gap-3 shadow-sm"
        >
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-[#FF5A36] text-white flex items-center justify-center shrink-0">
              <Sparkles className="w-5 h-5" />
            </div>
            <div>
              <p className="text-[13px] font-black text-[#1E1B2E]">
                Showing {events.length} of {totalEvents} updates
              </p>
              <p className="text-[12px] font-semibold text-[#74736D]">
                Upgrade to Pro to view your entire announcement history.
              </p>
            </div>
          </div>
          <Link
            href="/settings"
            className="min-h-[48px] px-4 rounded-xl bg-[#FF5A36] text-white text-xs font-black flex items-center shrink-0 shadow-sm active:scale-95 transition-all"
          >
            Upgrade
          </Link>
        </motion.div>
      )}

      <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-3">
        {selectionMode ? (
          <div className="flex items-center justify-between rounded-2xl bg-white p-3 shadow-sm border border-[var(--border-soft)]">
            <span className="text-xs font-bold text-[var(--text-2)]">{selectedIds.size} selected</span>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setDeleteConfirmOpen(true)}
                className="min-h-[48px] px-3 rounded-xl bg-[#FEE2E2] text-[#B91C1C] text-xs font-bold flex items-center gap-1.5"
              >
                <Trash2 className="w-4 h-4" /> Delete
              </button>
              <button
                onClick={cancelSelection}
                className="min-h-[48px] px-3 rounded-xl bg-[#F4F3EF] text-[#374151] text-xs font-bold"
              >
                Cancel
              </button>
            </div>
          </div>
        ) : (
          <>
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
            <div className="flex flex-wrap items-center gap-2">
              <div className="relative" data-filter-dropdown>
                <button
                  onClick={() => setFilterOpen(!filterOpen)}
                  className="min-h-[48px] inline-flex items-center gap-1.5 rounded-full border border-[var(--border-soft)] bg-[#F4F3EF] px-4 py-1.5 text-xs font-bold text-[var(--text-2)] hover:border-[#E9E9E6] hover:bg-white transition-all whitespace-nowrap"
                >
                  <span>{FILTER_LABELS[active]}</span>
                  <ChevronDown className={`w-3.5 h-3.5 transition-transform ${filterOpen ? 'rotate-180' : ''}`} />
                </button>
                {filterOpen && (
                  <div className="absolute left-0 top-full mt-1 z-30 rounded-[16px] border border-[var(--border-soft)] bg-white p-1 shadow-[0_18px_40px_rgba(0,0,0,0.08)] min-w-[160px]">
                    {FILTERS.map((f) => (
                      <button
                        key={f}
                        onClick={() => { setActive(f); setFilterOpen(false); }}
                        className={`w-full text-left px-3 py-2 rounded-[12px] text-xs font-bold transition-colors whitespace-nowrap ${
                          active === f
                            ? 'bg-[#FFF0EB] text-[#FF5A36]'
                            : 'text-[var(--text-2)] hover:bg-[#F4F3EF]'
                        }`}
                      >
                        {FILTER_LABELS[f]}
                      </button>
                    ))}
                  </div>
                )}
              </div>
              <div className="relative" data-sort-dropdown>
                <button
                  onClick={() => setSortOpen((p) => !p)}
                  className="min-h-[48px] inline-flex items-center gap-1.5 rounded-full border border-[var(--border-soft)] bg-[#F4F3EF] px-4 py-1.5 text-xs font-bold text-[var(--text-2)] hover:border-[#E9E9E6] hover:bg-white transition-all whitespace-nowrap"
                >
                  <ArrowUpDown className="w-3.5 h-3.5" />
                  {SORT_LABELS[sortOrder]}
                </button>
                {sortOpen && (
                  <div className="absolute right-0 top-full mt-1 z-30 rounded-[16px] border border-[var(--border-soft)] bg-white p-1 shadow-[0_18px_40px_rgba(0,0,0,0.08)] min-w-[160px]">
                    {(Object.entries(SORT_LABELS) as [SortOrder, string][]).map(([key, label]) => (
                      <button
                        key={key}
                        onClick={() => { changeSortOrder(key); setSortOpen(false); }}
                        className={`w-full text-left px-3 py-2 rounded-[12px] text-xs font-bold transition-colors whitespace-nowrap ${
                          sortOrder === key
                            ? 'bg-[#FFF0EB] text-[#FF5A36]'
                            : 'text-[var(--text-2)] hover:bg-[#F4F3EF]'
                        }`}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </>
        )}
      </motion.div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        <AnimatePresence mode="popLayout">
          {filtered.map((u, i) => {
            const meta = TYPE_META[u.event_type];
            const s = TYPE_STYLE[u.event_type];
            const days = daysLeft(u.date_time);
            const isPast = days < 0;
            const isExpanded = expandedPast === u.id;
            const isSelected = selectedIds.has(u.id);
            return (
              <motion.article
                key={u.id}
                layout
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: isPast && !isExpanded ? 0.45 : 1, y: 0 }}
                exit={{ opacity: 0, scale: 0.97 }}
                transition={{ delay: i * 0.05, ease: [0.16, 1, 0.3, 1] }}
                onPointerDown={() => startLongPress(u.id)}
                onPointerUp={clearLongPress}
                onPointerLeave={clearLongPress}
                onContextMenu={(event) => event.preventDefault()}
                onClick={() => {
                  if (longPressTriggered.current) {
                    longPressTriggered.current = false;
                    return;
                  }
                  if (selectionMode) {
                    toggleSelected(u.id);
                  } else {
                    setSelectedEvent(u);
                  }
                }}
                className={`clay-card relative p-4 hover:-translate-y-0.5 transition-all duration-200 cursor-pointer ${isPast && !isExpanded ? 'opacity-45 grayscale-[0.3]' : ''} ${isExpanded ? 'ring-2 ring-[var(--primary)]/30' : ''} ${isSelected ? 'ring-2 ring-[var(--primary)]' : ''}`}
              >
                {selectionMode && (
                  <span className="absolute right-4 top-4 flex h-7 w-7 items-center justify-center rounded-full bg-white shadow-sm" aria-hidden="true">
                    {isSelected ? <span className="flex h-6 w-6 items-center justify-center rounded-full bg-[var(--primary)] text-white"><Check className="h-4 w-4" /></span> : <Circle className="h-6 w-6 text-[var(--text-3)]" />}
                  </span>
                )}
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
                      {Number.isFinite(days) && (
                        <span className="text-[10px] font-bold tabular-nums text-[var(--text-3)]">
                          {days < 0 ? `${Math.abs(days)}d ago` : days === 0 ? 'Due now' : `${days}d left`}
                        </span>
                      )}
                      {u.needs_review && (
                        <span className="badge bg-[#FFF8EE] text-[#D97706] border border-[#FFE2B8] text-[9px] font-black">
                          REVIEW
                        </span>
                      )}
                    </div>
                    <p className="text-sm font-black tracking-[-0.01em] text-[var(--text-1)]">{u.title}</p>
                    {u.description && (
                      <p className="body-sm text-[var(--text-2)] mt-1 leading-relaxed line-clamp-2">{u.description}</p>
                    )}
                    <div className="flex flex-wrap items-center justify-between gap-2 mt-2 text-xs text-[var(--text-3)] font-semibold">
                      <div className="flex flex-wrap items-center gap-2">
                        {u.date_time && (
                          <span className="flex items-center gap-1">
                            <Clock className="w-3 h-3" />{formatDateTime(u.date_time, u.date_precision)}
                          </span>
                        )}
                        {u.venue && (
                          <span className="flex items-center gap-1">
                            <MapPin className="w-3 h-3" />{u.venue}
                          </span>
                        )}
                      </div>
                      {u.group_name && (
                        <span className="text-[11px] font-bold text-[var(--text-3)] truncate max-w-[150px]">
                          From {u.group_name}
                        </span>
                      )}
                    </div>

                    {u.needs_review && (
                      <div
                        className="mt-3 pt-2 border-t border-[var(--border-soft)] flex items-center justify-end gap-2"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <button
                          onClick={() => confirmEvent(u.id)}
                          className="min-h-[48px] px-3 rounded-xl bg-[#10B981] text-white text-xs font-bold flex items-center gap-1 shadow-sm active:scale-95 transition-all"
                        >
                          <Check className="w-3.5 h-3.5" /> Confirm
                        </button>
                        <button
                          onClick={() => setSelectedEvent(u)}
                          className="min-h-[48px] px-3 rounded-xl bg-[#F4F3EF] text-[#374151] text-xs font-bold active:scale-95 transition-all"
                        >
                          Review & Edit
                        </button>
                      </div>
                    )}
                  </div>
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

      {deleteConfirmOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-[#1E1B2E]/35 px-5 backdrop-blur-sm"
          role="presentation"
          onClick={() => setDeleteConfirmOpen(false)}
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.96, y: 8 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            role="dialog"
            aria-modal="true"
            className="w-full max-w-sm rounded-[28px] bg-white p-6 shadow-2xl border border-[var(--border-soft)]"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="text-lg font-black text-[var(--text-1)]">Delete {selectedIds.size} updates?</h3>
            <p className="body-sm text-[var(--text-2)] mt-2">
              This will remove the selected announcements from your feed.
            </p>
            <div className="mt-6 flex gap-2">
              <button
                type="button"
                onClick={() => setDeleteConfirmOpen(false)}
                className="min-h-12 flex-1 rounded-[14px] border border-[var(--border)] px-4 text-sm font-black text-[var(--text-2)] transition-colors hover:bg-[var(--surface-2)]"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleDeleteSelected}
                className="min-h-12 flex-1 rounded-[14px] bg-[var(--danger)] px-4 text-sm font-black text-white transition-colors hover:brightness-95"
              >
                Delete
              </button>
            </div>
          </motion.div>
        </div>
      )}

      {/* Event Detail Modal */}
      {selectedEvent && (
        <EventDetailModal
          event={selectedEvent}
          onClose={() => setSelectedEvent(null)}
        />
      )}
    </div>
  );
}

'use client';
import React, { useEffect, useMemo, useRef, useState } from 'react';
import { motion, useInView, useReducedMotion, useSpring, useTransform, useMotionValue } from 'framer-motion';
import Link from 'next/link';
import { useAppStore } from '@/lib/store';
import type { AcademicEvent } from '@/lib/events';
import {
  TYPE_META, daysLeft, formatDateTime, relativeDay, urgencyTone,
  cascadeTone, sortBySoonest,
} from '@/lib/events';
import ProfileAvatar from '@/components/profile-avatar';
import EventDetailModal from '@/components/dashboard/event-detail-modal';
import { YTPullToRefresh } from '@/components/ui/yt-pull-to-refresh';
import {
  AlertTriangle, Sparkles, Bell, ChevronRight, Calendar,
  Zap, CheckCircle2, FileText, ArrowUpRight, Flame,
  CalendarDays, Plus, WifiOff, ShieldAlert, Moon, Smartphone, Wifi, Clock, Users,
} from 'lucide-react';

/* ────────────────────────────────────────────────────────────
   Motion presets
   ──────────────────────────────────────────────────────────── */
const EASE = [0.16, 1, 0.3, 1] as const;
const FADE = (i = 0) => ({
  initial: { opacity: 0, y: 18 },
  animate: { opacity: 1, y: 0 },
  transition: { delay: i * 0.07, duration: 0.55, ease: EASE },
});

import { TiltCard, Ring, SectionHead, StickyNote, CoverageBanner } from '@/components/dashboard/dashboard-components';
import { formatTimeAgo } from '@/lib/datetime';


/* ────────────────────────────────────────────────────────────
   Page
   ──────────────────────────────────────────────────────────── */

export default function DashboardPage() {
  const {
    events, fetchEvents, user, groups, fetchGroups,
    unreadNotificationCount, fetchUnreadCount, nightBrief, fetchNightBrief,
    widgetData, fetchWidgetData, setAiPopupOpen,
  } = useAppStore();
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);
  const [selectedEvent, setSelectedEvent] = useState<AcademicEvent | null>(null);
  const hasLoadedOnce = useRef(false);

  useEffect(() => {
    let mounted = true;
    if (!hasLoadedOnce.current) {
      Promise.all([
        fetchEvents({ limit: 24 }),
        fetchGroups(),
        fetchUnreadCount(),
        fetchNightBrief(),
        fetchWidgetData(),
      ]).finally(() => {
        if (mounted) {
          setIsLoading(false);
          hasLoadedOnce.current = true;
        }
      });
      // Only run the full reload once; pull-to-refresh handles updates
    } else {
      if (mounted) setIsLoading(false);
    }
    return () => { mounted = false; };
  }, [fetchEvents, fetchGroups, fetchUnreadCount, fetchNightBrief, fetchWidgetData]);

  const handleRefresh = async () => {
    setIsRefreshing(true);
    try {
      await Promise.all([
        fetchEvents({ limit: 24 }),
        fetchGroups(),
        fetchUnreadCount(),
        fetchNightBrief(),
        fetchWidgetData(),
      ]);
    } finally {
      setIsRefreshing(false);
    }
  };

  const data: AcademicEvent[] = useMemo(() => events as AcademicEvent[], [events]);

  // Filter out past deadlines — no need to show them on the dashboard.
  const upcoming = useMemo(
    () => data.filter((e) => daysLeft(e.date_time) >= 0),
    [data],
  );

  const sorted = useMemo(() => [...upcoming].sort(sortBySoonest), [upcoming]);

  // Cascade = top upcoming actionable items (exclude INFO noise per PRD).
  const cascade = useMemo(
    () => sorted.filter((e) => e.event_type !== 'INFO').slice(0, 3),
    [sorted],
  );

  // Auto-cycle cascade cards every 5 seconds
  useEffect(() => {
    if (cascade.length <= 1) return;

    const interval = setInterval(() => {
      setActiveIndex((prev) => (prev + 1) % cascade.length);
    }, 5000);

    return () => clearInterval(interval);
  }, [cascade.length, activeIndex]);

  const latestEvents = useMemo(
    () =>
      [...upcoming]
        .sort((a, b) => new Date(b.created_at || 0).getTime() - new Date(a.created_at || 0).getTime())
        .slice(0, 3),
    [upcoming],
  );

  const deadlines = useMemo(
    () => sorted.filter((e) => e.event_type === 'DEADLINE').slice(0, 4),
    [sorted],
  );

  const name = user?.full_name ?? 'Student';
  const firstName = name.split(' ')[0] || 'Student';
  const email = user?.email;
  const hasGroups = groups.length > 0;
  const degradedGroups = groups.filter((g) => g.coverage_state !== 'ACTIVE');

  const quickLinks = [
    { icon: Clock, label: 'Reminders', href: '/reminders', fg: '#8A5CF5', dim: '#EBE5FC' },
    { icon: Users, label: 'Groups', href: '/groups', fg: '#2A9D8F', dim: '#E1F4F0' },
  ];

  return (
    <YTPullToRefresh onRefresh={handleRefresh} isRefreshing={isRefreshing}>
      <div className="app-page relative z-10 space-y-2 pb-24">
        <motion.div {...FADE(0)} className="flex items-center justify-between gap-4 pt-1 px-2">
        <div className="flex min-w-0 items-center gap-3">
          <Link
            href="/profile"
            className="h-10 w-10 shrink-0 overflow-hidden rounded-[16px] bg-[#D9F1EC] shadow-[inset_0_7px_12px_rgba(255,255,255,0.72),0_14px_28px_rgba(30,30,30,0.08)] ring-2 ring-[#FF5A36] ring-offset-2 ring-offset-[#FBFBFA] transition-transform active:scale-[0.98]"
            aria-label="Open profile"
          >
            <ProfileAvatar name={name} email={email} className="h-full w-full object-cover" />
          </Link>
          <div className="min-w-0">
            <h1 className="truncate text-[18px] font-black leading-none tracking-[-0.04em] text-[#171717]">
              <span className="text-[#686862]">Hi, </span>
              <span>{firstName}</span>
              <span className="text-[#FF5A36]">.</span>
            </h1>
            <p className="mt-1 text-[11px] font-bold uppercase tracking-wider text-[#A3A29C]">
              {new Date().toLocaleDateString('en-US', { timeZone: 'Africa/Lagos', weekday: 'long', month: 'short', day: 'numeric' })}
            </p>
          </div>
        </div>
        <Link
          href="/notifications"
          className="relative flex h-10 w-10 shrink-0 items-center justify-center rounded-[16px] bg-white text-[#171717] shadow-[inset_0_7px_12px_rgba(255,255,255,0.72),0_14px_28px_rgba(30,30,30,0.08)] transition-transform hover:-translate-y-0.5 active:scale-[0.98]"
          aria-label="Open notifications"
        >
          <Bell className="h-5 w-5" strokeWidth={2.4} />
          {unreadNotificationCount > 0 && (
            <span className="absolute -right-1 -top-1 flex h-5 min-w-5 items-center justify-center rounded-full bg-[#FF5A36] px-1 text-[10px] font-black text-white ring-2 ring-white">
              {unreadNotificationCount > 9 ? '9+' : unreadNotificationCount}
            </span>
          )}
        </Link>
      </motion.div>

      {/* Coverage banners */}
      {degradedGroups.length > 0 && (
        <motion.div {...FADE(0)} className="space-y-2">
          {degradedGroups.map((g) => (
            <CoverageBanner key={g.id} state={g.coverage_state} name={g.group_name} />
          ))}
        </motion.div>
      )}

      {/* First-run: no groups linked yet */}
      {isLoading ? null : !hasGroups && (
        <motion.div {...FADE(1)}>
          <Link
            href="/groups"
            className="group flex items-center gap-4 rounded-[28px] border border-[#FFD8CD] bg-gradient-to-br from-[#FFF0EB] to-[#FFFFFF] p-5 shadow-[0_18px_40px_rgba(255,90,54,0.08)] transition-all hover:-translate-y-0.5"
          >
            <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-[20px] bg-[#FF5A36] text-white shadow-[0_12px_24px_rgba(255,90,54,0.22)]">
              <Plus className="h-6 w-6" />
            </div>
            <div className="flex-1 min-w-0">
              <h2 className="text-[15px] font-black tracking-[-0.02em] text-[#171717]">Link your first class chat</h2>
              <p className="mt-0.5 text-xs font-semibold text-[#74736D]">Paste a WhatsApp invite link and Knowtis starts surfacing deadlines.</p>
            </div>
            <ArrowUpRight className="h-5 w-5 shrink-0 text-[#FF5A36] transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
          </Link>
        </motion.div>
      )}

      {/* ── Sticky Note Cascade (hero) ──────────────────────── */}
      <motion.header {...FADE(1)} className="flex flex-col items-center">
        {cascade.length > 0 ? (
          <>
            <div className="relative w-full h-[176px] sm:h-[196px]">
              {cascade.map((e, i) => (
                <StickyNote
                  key={e.id}
                  e={e}
                  index={i}
                  activeIndex={activeIndex}
                  setActiveIndex={setActiveIndex}
                  total={cascade.length}
                  onSelect={setSelectedEvent}
                />
              ))}
            </div>
            {/* Dots Indicator */}
            {cascade.length > 1 && (
              <div className="flex justify-center gap-1.5 mt-4 relative z-20">
                {cascade.map((_, i) => (
                  <button
                    key={i}
                    onClick={() => setActiveIndex(i)}
                    className={`h-1.5 rounded-full transition-all duration-300 ${
                      activeIndex === i ? 'w-5 bg-[#FF5A36]' : 'w-1.5 bg-[#FF5A36]/20'
                    }`}
                    aria-label={`Go to slide ${i + 1}`}
                  />
                ))}
              </div>
            )}
          </>
        ) : (
          <div className="relative overflow-hidden rounded-[36px] bg-[#F4F3EF] border border-[#E9E9E6] p-5 shadow-sm sm:p-6 h-[250px] flex flex-col items-center justify-center text-center w-full">
            <Sparkles className="w-8 h-8 text-[#171717]/20 mb-3" />
            <p className="text-[22px] font-black tracking-[-0.04em] text-[#171717]/40">You&apos;re all caught up.</p>
            <p className="text-[15px] font-bold text-[#171717]/30 mt-1">The academic noise is quiet today.</p>
          </div>
        )}
      </motion.header>

      {isLoading ? (
        <motion.div {...FADE(1)} className="space-y-8">
          <div className="clay-card-strong p-5 h-[140px] skeleton" />
          <div className="space-y-3">
            <div className="h-6 w-32 skeleton-soft rounded-md" />
            <div className="clay-card h-[72px] skeleton" />
            <div className="clay-card h-[72px] skeleton" />
          </div>
          <div className="space-y-3">
            <div className="h-6 w-32 skeleton-soft rounded-md" />
            <div className="grid sm:grid-cols-2 gap-3">
              <div className="clay-card h-[88px] skeleton" />
              <div className="clay-card h-[88px] skeleton" />
            </div>
          </div>
        </motion.div>
      ) : (
        <>
        {/* ── Today's Briefing / Night Brief ──────────────── */}
        {nightBrief?.summary && (
          <motion.section {...FADE(1.5)} aria-label="Daily Briefing Summary" className="mb-4">
            <div className="relative overflow-hidden rounded-[32px] border border-[#FAD7CD]/40 bg-gradient-to-br from-[#FFF9F6] via-white to-[#FBFBFA] p-5 shadow-[0_24px_48px_rgba(255,90,54,0.04),inset_0_1px_0_rgba(255,255,255,1)]">
              {/* Decorative light */}
              <div className="pointer-events-none absolute -right-10 -top-10 h-40 w-40 rounded-full bg-[#FFF0EB]/40 blur-[40px]" />
              
              <div className="flex items-center gap-2 mb-4">
                <div className="flex h-8 w-8 -rotate-3 items-center justify-center rounded-xl bg-[#FF5A36] shadow-sm text-white">
                  <Sparkles className="w-4 h-4" />
                </div>
                <h2 className="text-xs font-black uppercase tracking-[0.08em] text-[#686862]">Your Daily Briefing</h2>
              </div>
              
              <p className="text-[15px] font-semibold leading-relaxed text-[#171717] max-w-[65ch]">
                {nightBrief.summary}
              </p>
              
              <div className="mt-5 flex flex-wrap gap-2 items-center">
                {nightBrief.deadline_count > 0 && (
                  <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-[#FFF0EB] border border-[#FFD8CD] text-[11px] font-black text-[#FF5A36]">
                    <Flame className="w-3.5 h-3.5" /> {nightBrief.deadline_count} deadline{nightBrief.deadline_count > 1 ? 's' : ''}
                  </span>
                )}
                {nightBrief.alert_count > 0 && (
                  <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-red-50 border border-red-100 text-[11px] font-black text-red-600">
                    <AlertTriangle className="w-3.5 h-3.5" /> {nightBrief.alert_count} alert{nightBrief.alert_count > 1 ? 's' : ''}
                  </span>
                )}
                {nightBrief.event_count > 0 && (
                  <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-blue-50 border border-blue-100 text-[11px] font-black text-blue-600">
                    <CalendarDays className="w-3.5 h-3.5" /> {nightBrief.event_count} update{nightBrief.event_count > 1 ? 's' : ''}
                  </span>
                )}
                
                <button
                  onClick={(e) => {
                    e.preventDefault();
                    setAiPopupOpen(true);
                  }}
                  className="ml-auto inline-flex items-center gap-1 text-[11px] font-black text-[#FF5A36] hover:underline"
                >
                  Discuss with AI <ArrowUpRight className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          </motion.section>
        )}

        {/* ── Latest from Groups ───────────────────────────── */}
        <motion.section {...FADE(2)} aria-label="Latest Updates">
          <SectionHead title="Latest from Groups" href="/updates" cta="See all" />
          <div className="space-y-3">
            {latestEvents.length === 0 ? (
              <div className="clay-card p-6 text-center">
                <CheckCircle2 className="mx-auto mb-2 h-7 w-7 text-[var(--success)]" />
                <p className="text-sm font-bold text-[var(--text-2)]">No updates received yet.</p>
              </div>
            ) : latestEvents.map((e, i) => {
              const days = daysLeft(e.date_time);
              const tone = urgencyTone(days);
              const meta = TYPE_META[e.event_type];
              return (
                <motion.div
                  key={e.id}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.22 + i * 0.08, ease: EASE }}
                >
                  <a
                    href="#"
                    onClick={(ev) => { ev.preventDefault(); setSelectedEvent(e); }}
                    className="group flex items-center gap-3.5 rounded-[28px] border border-transparent bg-white/60 p-4 shadow-[0_18px_40px_rgba(0,0,0,0.04),inset_0_1px_0_rgba(255,255,255,1)] backdrop-blur-md transition-all hover:-translate-y-1 hover:border-white/80 hover:bg-white hover:shadow-[0_24px_48px_rgba(0,0,0,0.08)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#FF5A36] cursor-pointer"
                  >
                    <div
                      className="relative flex h-11 w-11 shrink-0 items-center justify-center rounded-[18px] shadow-sm transition-transform duration-300 group-hover:scale-110 group-hover:-rotate-3"
                      style={{ background: tone.dim }}
                    >
                      <meta.icon className="w-5 h-5 relative z-10 transition-transform duration-300 group-hover:scale-110" style={{ color: tone.color }} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="badge" style={{ background: tone.dim, color: tone.color, borderColor: 'transparent' }}>
                          {meta.tag}
                        </span>
                        {e.course_code && (
                          <span className="text-[11px] font-bold text-[var(--text-3)]">{e.course_code}</span>
                        )}
                        {e.group_name && (
                          <span className="text-[10px] font-bold text-[var(--text-3)] truncate max-w-[120px]">
                            {e.group_name}
                          </span>
                        )}
                      </div>
                      <p className="truncate text-sm font-black leading-snug tracking-[-0.02em] text-[#171717]">{e.title}</p>
                    </div>
                    <div className="text-right shrink-0">
                      <p className="text-[10px] font-black uppercase tracking-wider text-[var(--text-3)] bg-[#F0F0ED] px-2 py-0.5 rounded-full">
                        {formatTimeAgo(e.created_at)}
                      </p>
                      <ChevronRight className="w-4 h-4 text-[var(--text-3)] ml-auto mt-1 group-hover:translate-x-0.5 transition-transform" />
                    </div>
                  </a>
                </motion.div>
              );
            })}
          </div>
        </motion.section>

        {/* ── On the Horizon (Deadlines) ──────────────────── */}
        {deadlines.length > 0 && (
          <motion.section {...FADE(3)} aria-label="On the Horizon">
            <SectionHead title="On the Horizon" href="/calendar" cta="Calendar" />
            <div className="grid sm:grid-cols-2 gap-3">
              {deadlines.map((d, i) => {
                const days = daysLeft(d.date_time);
                const tone = urgencyTone(days);
                const pct = Math.max(8, Math.min(96, 100 - Math.max(0, days) * 11));
                return (
                  <motion.div
                    key={d.id}
                    initial={{ opacity: 0, y: 14 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.24 + i * 0.09, ease: EASE }}
                  >
                    <TiltCard
                      onClick={() => setSelectedEvent(d)}
                      className="flex h-full cursor-pointer items-center gap-4 rounded-[28px] border border-white bg-white/60 p-4 shadow-[0_18px_40px_rgba(0,0,0,0.04),inset_0_1px_0_rgba(255,255,255,1)] backdrop-blur-md"
                    >
                    <div className="relative grid place-items-center">
                      <Ring pct={pct} color={tone.color} />
                      <span className="absolute text-[11px] font-black tabular-nums" style={{ color: tone.color }}>
                        {days < 0 ? '!' : days === 0 ? '·' : `${days}d`}
                      </span>
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="truncate text-sm font-black tracking-[-0.02em] text-[#171717]">{d.title}</p>
                      <p className="text-xs text-[var(--text-3)] font-semibold mt-0.5">
                        {d.course_code ? `${d.course_code} · ` : ''}Due {formatDateTime(d.date_time, d.date_precision)}
                      </p>
                      <span className="mt-2 inline-block rounded-[8px] px-2 py-0.5 text-[10px] font-black uppercase tracking-wide" style={{ background: tone.dim, color: tone.color }}>
                        {tone.label}
                      </span>
                    </div>
                    </TiltCard>
                  </motion.div>
                );
              })}
            </div>
          </motion.section>
        )}

        {/* ── Quick access / Reminders ────────────────────── */}
        <motion.section {...FADE(3.5)} aria-label="Quick access" className="pt-1">
          <SectionHead title="Quick access" />
          <div className="grid grid-cols-2 gap-3">
            {quickLinks.map((q, i) => (
              <motion.div
                key={q.label}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.26 + i * 0.08, ease: EASE }}
              >
                <Link
                  href={q.href}
                  className="group flex items-center justify-between gap-2.5 rounded-[24px] border border-white/60 bg-white/60 p-3 sm:p-4 shadow-[0_18px_40px_rgba(0,0,0,0.04),inset_0_1px_0_rgba(255,255,255,1)] backdrop-blur-md transition-all hover:-translate-y-1 hover:border-white hover:bg-white hover:shadow-[0_24px_48px_rgba(0,0,0,0.08)] active:scale-[0.98]"
                >
                  <div className="flex items-center gap-2.5 min-w-0">
                    <div
                      className="flex h-10 w-10 shrink-0 items-center justify-center rounded-[16px] shadow-sm transition-transform duration-300 group-hover:scale-110 group-hover:-rotate-3"
                      style={{ background: q.dim }}
                    >
                      <q.icon className="h-5 w-5 transition-transform duration-300 group-hover:scale-110" style={{ color: q.fg }} />
                    </div>
                    <span className="text-[13px] sm:text-sm font-black tracking-[-0.02em] text-[#171717] whitespace-nowrap">
                      {q.label}
                    </span>
                  </div>
                  <ChevronRight className="h-4 w-4 shrink-0 text-[var(--text-3)] group-hover:translate-x-0.5 transition-transform" />
                </Link>
              </motion.div>
            ))}
          </div>
        </motion.section>

        </>
      )}
      {selectedEvent && (
        <EventDetailModal
          event={selectedEvent}
          onClose={() => setSelectedEvent(null)}
        />
      )}
      </div>
    </YTPullToRefresh>
  );
}

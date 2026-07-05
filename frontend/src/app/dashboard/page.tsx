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
import {
  AlertTriangle, Sparkles, Bell, ChevronRight, Calendar,
  Zap, CheckCircle2, FileText, ArrowUpRight, Flame, BookMarked,
  CalendarDays, Plus, Link2, WifiOff, ShieldAlert, Moon, Smartphone, Wifi,
  Clock,
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

/* ────────────────────────────────────────────────────────────
   Count-up number (respects reduced motion)
   ──────────────────────────────────────────────────────────── */
function CountUp({ value, duration = 1100 }: { value: number; duration?: number }) {
  const reduce = useReducedMotion();
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true, margin: '-40px' });
  const animate = inView && !reduce;
  const [n, setN] = useState(() => (reduce ? value : 0));

  useEffect(() => {
    if (!animate) return;
    let raf = 0;
    const start = performance.now();
    const tick = (t: number) => {
      const p = Math.min(1, (t - start) / duration);
      const eased = 1 - Math.pow(1 - p, 3);
      setN(Math.round(eased * value));
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [animate, value, duration]);

  const display = reduce ? value : n;
  return <span ref={ref} className="tabular-nums">{display}</span>;
}

/* ────────────────────────────────────────────────────────────
   Tilt Card Wrapper
   ──────────────────────────────────────────────────────────── */
function TiltCard({ children, className, href, style: cardStyle }: { children: React.ReactNode; className?: string; href?: string; style?: React.CSSProperties }) {
  const x = useMotionValue(0);
  const y = useMotionValue(0);
  const reduce = useReducedMotion();
  const mouseXSpring = useSpring(x, { stiffness: 300, damping: 20 });
  const mouseYSpring = useSpring(y, { stiffness: 300, damping: 20 });
  const rotateX = useTransform(mouseYSpring, [-0.5, 0.5], ['6deg', '-6deg']);
  const rotateY = useTransform(mouseXSpring, [-0.5, 0.5], ['-6deg', '6deg']);

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (reduce) return;
    const rect = e.currentTarget.getBoundingClientRect();
    x.set((e.clientX - rect.left) / rect.width - 0.5);
    y.set((e.clientY - rect.top) / rect.height - 0.5);
  };
  const handleMouseLeave = () => { x.set(0); y.set(0); };

  const motionStyle = reduce ? cardStyle : { ...cardStyle, rotateX, rotateY, transformPerspective: 1000 };

  const content = (
    <motion.div
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
      style={motionStyle}
      className={className}
      whileHover={{ scale: 1.02 }}
      transition={{ type: 'spring', stiffness: 400, damping: 25 }}
    >
      {children}
    </motion.div>
  );

  return href ? <Link href={href} className="block focus-visible:outline-none">{content}</Link> : content;
}

/* ────────────────────────────────────────────────────────────
   Animated progress ring
   ──────────────────────────────────────────────────────────── */
function Ring({ pct, color, size = 46 }: { pct: number; color: string; size?: number }) {
  const reduce = useReducedMotion();
  const r = (size - 6) / 2;
  const c = 2 * Math.PI * r;
  const target = c - (pct / 100) * c;
  return (
    <svg width={size} height={size} className="shrink-0 -rotate-90 drop-shadow-md" aria-hidden>
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="rgba(15,23,42,0.06)" strokeWidth={4} />
      <motion.circle
        cx={size / 2} cy={size / 2} r={r} fill="none" stroke={color} strokeWidth={4}
        strokeLinecap="round" strokeDasharray={c}
        initial={{ strokeDashoffset: reduce ? target : c }}
        whileInView={{ strokeDashoffset: target }}
        viewport={{ once: true }}
        transition={{ duration: 1, ease: EASE, delay: 0.2 }}
      />
    </svg>
  );
}

/* ────────────────────────────────────────────────────────────
   Section header
   ──────────────────────────────────────────────────────────── */
function SectionHead({ title, href, cta }: { title: string; href: string; cta: string }) {
  return (
    <div className="flex items-center justify-between mb-3">
      <h2 className="text-[20px] font-black tracking-[-0.04em] text-[#171717]">{title}</h2>
      <Link
        href={href}
        className="flex items-center gap-0.5 rounded-full bg-white px-3 py-1.5 text-xs font-black text-[#FF5A36] shadow-[0_10px_22px_rgba(30,30,30,0.06)] transition-all hover:gap-1.5 active:scale-[0.98]"
      >
        {cta} <ChevronRight className="w-3.5 h-3.5" />
      </Link>
    </div>
  );
}

function StickyNote({
  e,
  index,
  activeIndex,
  setActiveIndex,
  total,
}: {
  e: AcademicEvent;
  index: number;
  activeIndex: number;
  setActiveIndex: (idx: number) => void;
  total: number;
}) {
  const tone = cascadeTone(e);
  const meta = TYPE_META[e.event_type];
  
  // Calculate relative position where 0 is front, 1 is middle, 2 is back
  const position = (index - activeIndex + total) % total;
  
  const rot = position === 0 ? -2 : position % 2 === 0 ? 4 : -5;
  const offsetY = position * 18;
  const scale = position === 0 ? 1 : 1 - position * 0.05;
  const z = total - position;

  const isInitial = useRef(true);

  useEffect(() => {
    isInitial.current = false;
  }, []);

  const transition = isInitial.current
    ? { delay: index * 0.1, duration: 0.5, ease: EASE }
    : { type: 'spring' as const, stiffness: 300, damping: 25 };

  const handleClick = (ev: React.MouseEvent) => {
    if (position !== 0) {
      ev.preventDefault();
      setActiveIndex(index);
    }
  };

  return (
    <Link
      href="/updates"
      onClick={handleClick}
      className="absolute inset-x-0 mx-auto block focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#FF5A36] rounded-[28px]"
      style={{ zIndex: z, width: 'min(100%, 440px)' }}
      aria-label={`${meta.tag}: ${e.title}`}
    >
      <motion.div
        initial={{ opacity: 0, y: 24, rotate: 0 }}
        animate={{ opacity: 1, y: offsetY, rotate: rot, scale }}
        transition={transition}
        whileHover={{ 
          y: offsetY - (position === 0 ? 6 : 3), 
          scale: scale * (position === 0 ? 1.02 : 1.01) 
        }}
        className="relative mx-auto w-full rounded-[28px] p-5 shadow-[0_24px_50px_rgba(30,30,30,0.12),inset_0_1px_0_rgba(255,255,255,0.6)] cursor-pointer"
        style={{ background: tone.bg }}
      >
        {/* Tape detail */}
        <span
          className="absolute -top-2 left-1/2 h-4 w-16 -translate-x-1/2 rounded-[3px] bg-white/55 shadow-sm"
          aria-hidden
        />
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-2">
            <span className="rounded-[10px] bg-white/70 px-2.5 py-1 text-[10px] font-black uppercase tracking-[0.08em] text-[#1E1B2E]">
              {meta.tag}
            </span>
            {e.course_code && (
              <span className="text-[12px] font-bold text-[#1E1B2E]/70">{e.course_code}</span>
            )}
          </div>
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-[14px] bg-white/70 shadow-sm">
            <meta.icon className="h-4 w-4 text-[#1E1B2E]" />
          </div>
        </div>

        <h2 className="mt-3 text-[22px] font-black leading-[1.1] tracking-[-0.03em] text-[#1E1B2E] line-clamp-2">
          {e.title}
        </h2>
        <div className="mt-2 flex items-center justify-between">
          <p className="text-xs font-bold text-[#1E1B2E]/70">{relativeDay(e.date_time)}</p>
          <p className="text-[11px] font-black uppercase tracking-wide text-[#1E1B2E]/50">{tone.label}</p>
        </div>
      </motion.div>
    </Link>
  );
}


/* ────────────────────────────────────────────────────────────
   Relative extraction time helper
   ──────────────────────────────────────────────────────────── */
function formatRelativeTime(iso?: string): string {
  if (!iso) return 'Just now';
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'Just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}


/* ────────────────────────────────────────────────────────────
   Coverage banner — calm system notice for degraded groups
   ──────────────────────────────────────────────────────────── */
function CoverageBanner({ state, name }: { state: string; name: string }) {
  const isPaused = state === 'PAUSED';
  const isDegraded = state === 'DEGRADED';
  const isRecovering = state === 'RECOVERING';
  if (!isPaused && !isDegraded && !isRecovering) return null;

  const cfg = isPaused
    ? { icon: WifiOff, text: 'paused', fg: 'var(--danger)' }
    : isRecovering
    ? { icon: ShieldAlert, text: 'recovering', fg: 'var(--warning)' }
    : { icon: ShieldAlert, text: 'degraded', fg: 'var(--warning)' };

  return (
    <div className="flex items-center gap-2.5 rounded-2xl border border-[var(--border-soft)] bg-white/70 px-4 py-2.5 backdrop-blur-md">
      <cfg.icon className="h-4 w-4 shrink-0" style={{ color: cfg.fg }} />
      <p className="text-xs font-semibold text-[var(--text-2)]">
        <span className="font-black text-[var(--text-1)]">{name}</span> monitoring is{' '}
        <span className="font-black" style={{ color: cfg.fg }}>{cfg.text}</span>.
        Some updates may be missing during this period.
      </p>
    </div>
  );
}





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
  const [activeIndex, setActiveIndex] = useState(0);

  useEffect(() => {
    let mounted = true;
    Promise.all([
      fetchEvents({ limit: 24 }),
      fetchGroups(),
      fetchUnreadCount(),
      fetchNightBrief(),
      fetchWidgetData(),
    ]).finally(() => { if (mounted) setIsLoading(false); });
    return () => { mounted = false; };
  }, [fetchEvents, fetchGroups, fetchUnreadCount, fetchNightBrief, fetchWidgetData]);

  const data: AcademicEvent[] = useMemo(() => events as AcademicEvent[], [events]);

  const sorted = useMemo(() => [...data].sort(sortBySoonest), [data]);

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

  const urgent = useMemo(
    () =>
      [...data]
        .filter((e) => e.event_type !== 'INFO' || e.urgency_score >= 0.6)
        .sort((a, b) => b.urgency_score - a.urgency_score)
        .slice(0, 3),
    [data],
  );

  const latestEvents = useMemo(
    () =>
      [...data]
        .sort((a, b) => new Date(b.created_at || 0).getTime() - new Date(a.created_at || 0).getTime())
        .slice(0, 3),
    [data],
  );

  const deadlines = useMemo(
    () => sorted.filter((e) => e.event_type === 'DEADLINE').slice(0, 4),
    [sorted],
  );

  const dueThisWeek = data.filter((e) => e.event_type === 'DEADLINE' && daysLeft(e.date_time) <= 7 && daysLeft(e.date_time) >= 0).length;
  const activeAlerts = data.filter((e) => e.event_type === 'ALERT').length;
  const upcomingEvents = data.filter((e) => e.event_type === 'EVENT').length;

  const name = user?.full_name ?? 'Student';
  const firstName = name.split(' ')[0] || 'Student';
  const email = user?.email;
  const hasGroups = groups.length > 0;
  const degradedGroups = groups.filter((g) => g.coverage_state !== 'ACTIVE');

  const stats = [
    { icon: Flame, label: 'Due this week', value: dueThisWeek, tint: '#FF5A36', dim: '#FFF0EB' },
    { icon: AlertTriangle, label: 'Active alerts', value: activeAlerts, tint: '#E54835', dim: '#FFF0EB' },
    { icon: CalendarDays, label: 'Upcoming events', value: upcomingEvents, tint: '#4285F4', dim: '#C6DDF6' },
  ];



  const quickLinks = [
    { icon: Clock, label: 'Reminders', href: '/reminders', fg: '#8A5CF5', dim: '#EBE5FC' },
    { icon: Link2, label: 'WhatsApp Groups', href: '/groups', fg: '#4285F4', dim: '#C6DDF6' },
  ];

  return (
    <div className="app-page relative z-10 space-y-6 pb-32">
      <motion.div {...FADE(0)} className="flex items-center justify-between gap-4 pt-2">
        <div className="flex min-w-0 items-center gap-3">
          <Link
            href="/profile"
            className="h-12 w-12 shrink-0 overflow-hidden rounded-[20px] bg-[#D9F1EC] shadow-[inset_0_7px_12px_rgba(255,255,255,0.72),0_14px_28px_rgba(30,30,30,0.08)] transition-transform active:scale-[0.98]"
            aria-label="Open profile"
          >
            <ProfileAvatar name={name} email={email} className="h-full w-full object-cover" />
          </Link>
          <div className="min-w-0">
            <h1 className="truncate text-[22px] font-black leading-none tracking-[-0.04em] text-[#171717]">
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
          className="relative flex h-12 w-12 shrink-0 items-center justify-center rounded-[20px] bg-white text-[#171717] shadow-[inset_0_7px_12px_rgba(255,255,255,0.72),0_14px_28px_rgba(30,30,30,0.08)] transition-transform hover:-translate-y-0.5 active:scale-[0.98]"
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
            <div className="relative w-full h-[200px] sm:h-[220px]">
              {cascade.map((e, i) => (
                <StickyNote
                  key={e.id}
                  e={e}
                  index={i}
                  activeIndex={activeIndex}
                  setActiveIndex={setActiveIndex}
                  total={cascade.length}
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
        {/* ── Stat ribbon ─────────────────────────────────── */}
        <motion.section {...FADE(1)} aria-label="Today's summary" className="mb-6">
          <div className="relative overflow-hidden rounded-[32px] border border-[#F0F0ED]/50 bg-white/70 p-5 shadow-[0_24px_54px_rgba(0,0,0,0.04),inset_0_1px_0_rgba(255,255,255,1)] backdrop-blur-xl">
            <div className="relative mb-4 flex items-center gap-2">
              <div className="flex h-8 w-8 -rotate-3 items-center justify-center rounded-2xl bg-[#FF5A36] shadow-[0_12px_24px_rgba(255,90,54,0.22),inset_0_5px_9px_rgba(255,255,255,0.28)]">
                <CalendarDays className="w-4 h-4 text-white" />
              </div>
              <p className="text-xs font-black uppercase tracking-[0.08em] text-[#686862]">Today&apos;s briefing</p>
            </div>
            <div className="grid grid-cols-3 gap-3 relative">
              {stats.map((s, i) => (
                <motion.div
                  key={s.label}
                  initial={{ opacity: 0, y: 12 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.25 + i * 0.09, ease: EASE }}
                  className="rounded-[24px] border border-white/50 p-3 shadow-sm"
                  style={{ background: s.dim }}
                >
                  <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-[16px] bg-white shadow-[0_8px_16px_rgba(30,30,30,0.06),inset_0_2px_4px_rgba(255,255,255,1)]">
                    <s.icon className="w-[18px] h-[18px]" style={{ color: s.tint }} />
                  </div>
                  <span className="text-[26px] font-black leading-none tracking-[-0.04em] text-[#171717]">
                    <CountUp value={s.value} />
                  </span>
                  <span className="mt-1 block text-[11px] font-black leading-tight text-[#686862]">{s.label}</span>
                </motion.div>
              ))}
            </div>
          </div>
        </motion.section>

        {/* ── Today's Briefing / Night Brief ──────────────── */}
        {nightBrief?.summary && (
          <motion.section {...FADE(1.5)} aria-label="Daily Briefing Summary" className="mb-6">
            <div className="relative overflow-hidden rounded-[32px] border border-[#FAD7CD]/40 bg-gradient-to-br from-[#FFF9F6] via-white to-[#FBFBFA] p-6 shadow-[0_24px_48px_rgba(255,90,54,0.04),inset_0_1px_0_rgba(255,255,255,1)]">
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

        {/* ── Urgent + Deadlines side by side on desktop ── */}
        <div className="lg:grid lg:grid-cols-2 lg:gap-6 space-y-8 lg:space-y-0">

          {/* Column 1: High Priority + Latest from Groups */}
          <div className="space-y-8">
            {/* ── Urgent ───────────────────────────────────────── */}
            <motion.section {...FADE(2)} aria-label="High Priority">
              <SectionHead title="High Priority" href="/updates" cta="See all" />
              <div className="space-y-3">
                {urgent.length === 0 ? (
                  <div className="clay-card p-6 text-center">
                    <CheckCircle2 className="mx-auto mb-2 h-7 w-7 text-[var(--success)]" />
                    <p className="text-sm font-bold text-[var(--text-2)]">Nothing urgent right now.</p>
                  </div>
                ) : urgent.map((e, i) => {
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
                      <Link
                        href="/updates"
                        className={`group flex items-center gap-3.5 rounded-[28px] border border-transparent bg-white/60 p-4 shadow-[0_18px_40px_rgba(0,0,0,0.04),inset_0_1px_0_rgba(255,255,255,1)] backdrop-blur-md transition-all hover:-translate-y-1 hover:border-white/80 hover:bg-white hover:shadow-[0_24px_48px_rgba(0,0,0,0.08)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#FF5A36] ${days <= 0 ? 'ring-1 ring-[#E54835] ring-offset-2 ring-offset-[#FBFBFA]' : ''}`}
                      >
                        <div
                          className="relative flex h-11 w-11 shrink-0 items-center justify-center rounded-[18px] shadow-sm transition-transform duration-300 group-hover:scale-110 group-hover:-rotate-3"
                          style={{ background: tone.dim }}
                        >
                          {days <= 0 && <span className="absolute inset-0 rounded-[20px] bg-[var(--danger)] opacity-[0.15] animate-ping" />}
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
                          </div>
                          <p className="truncate text-sm font-black leading-snug tracking-[-0.02em] text-[#171717]">{e.title}</p>
                        </div>
                        <div className="text-right shrink-0">
                          <p className="text-sm font-black tabular-nums" style={{ color: tone.color }}>
                            {days < 0 ? 'Overdue' : days === 0 ? 'Today' : `${days}d`}
                          </p>
                          <ChevronRight className="w-4 h-4 text-[var(--text-3)] ml-auto mt-0.5 group-hover:translate-x-0.5 transition-transform" />
                        </div>
                      </Link>
                    </motion.div>
                  );
                })}
              </div>
            </motion.section>

            {/* ── Latest from Groups ───────────────────────────── */}
            <motion.section {...FADE(2.5)} aria-label="Latest Updates">
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
                      transition={{ delay: 0.25 + i * 0.08, ease: EASE }}
                    >
                      <Link
                        href="/updates"
                        className="group flex items-center gap-3.5 rounded-[28px] border border-transparent bg-white/60 p-4 shadow-[0_18px_40px_rgba(0,0,0,0.04),inset_0_1px_0_rgba(255,255,255,1)] backdrop-blur-md transition-all hover:-translate-y-1 hover:border-white/80 hover:bg-white hover:shadow-[0_24px_48px_rgba(0,0,0,0.08)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#FF5A36]"
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
                          </div>
                          <p className="truncate text-sm font-black leading-snug tracking-[-0.02em] text-[#171717]">{e.title}</p>
                        </div>
                        <div className="text-right shrink-0">
                          <p className="text-[10px] font-black uppercase tracking-wider text-[var(--text-3)] bg-[#F0F0ED] px-2 py-0.5 rounded-full">
                            {formatRelativeTime(e.created_at)}
                          </p>
                          <ChevronRight className="w-4 h-4 text-[var(--text-3)] ml-auto mt-1 group-hover:translate-x-0.5 transition-transform" />
                        </div>
                      </Link>
                    </motion.div>
                  );
                })}
              </div>
            </motion.section>
          </div>

          {/* Column 2: On the Horizon */}
          <div className="space-y-8">
            {/* ── Deadlines (rings) ────────────────────────────── */}
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
                      <TiltCard className="flex h-full cursor-pointer items-center gap-4 rounded-[28px] border border-white bg-white/60 p-4 shadow-[0_18px_40px_rgba(0,0,0,0.04),inset_0_1px_0_rgba(255,255,255,1)] backdrop-blur-md">
                      <div className="relative grid place-items-center">
                        <Ring pct={pct} color={tone.color} />
                        <span className="absolute text-[11px] font-black tabular-nums" style={{ color: tone.color }}>
                          {days < 0 ? '!' : days === 0 ? '·' : `${days}d`}
                        </span>
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="truncate text-sm font-black tracking-[-0.02em] text-[#171717]">{d.title}</p>
                        <p className="text-xs text-[var(--text-3)] font-semibold mt-0.5">
                          {d.course_code ? `${d.course_code} · ` : ''}Due {formatDateTime(d.date_time)}
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
          </div>

        </div>

        {/* ── Quick access ─────────────────────────────────── */}
        <motion.section {...FADE(4)} aria-label="Quick access" className="pb-2 max-w-xl">
          <div className="flex items-center gap-2 mb-3">
            <BookMarked className="w-4 h-4 text-[var(--text-2)]" />
            <h2 className="text-[20px] font-black tracking-[-0.04em] text-[#171717]">Quick access</h2>
          </div>
          <div className="grid grid-cols-2 gap-3">
            {quickLinks.map((q, i) => (
              <motion.div
                key={q.label}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.3 + i * 0.07, ease: EASE }}
              >
                <TiltCard href={q.href} className="group flex flex-col items-center gap-2 rounded-[24px] border border-white/50 p-3.5 text-center shadow-sm transition-all hover:shadow-md" style={{ background: q.dim }}>
                  <div className="flex h-11 w-11 items-center justify-center rounded-[18px] bg-white shadow-[0_8px_16px_rgba(30,30,30,0.06),inset_0_2px_4px_rgba(255,255,255,1)] transition-transform duration-300 group-hover:scale-110 group-hover:-rotate-6">
                    <q.icon className="w-5 h-5 transition-transform duration-300 group-hover:scale-110" style={{ color: q.fg }} />
                  </div>
                  <span className="text-xs font-black text-[#171717]">{q.label}</span>
                </TiltCard>
              </motion.div>
            ))}
          </div>
        </motion.section>


        </>
      )}
    </div>
  );
}

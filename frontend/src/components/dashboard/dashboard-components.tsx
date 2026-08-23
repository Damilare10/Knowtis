'use client';
import React, { useEffect, useRef, useState } from 'react';
import { motion, useInView, useReducedMotion, useSpring, useTransform, useMotionValue } from 'framer-motion';
import Link from 'next/link';
import { ChevronRight, WifiOff, ShieldAlert } from 'lucide-react';
import type { AcademicEvent } from '@/lib/events';
import { TYPE_META, cascadeTone, relativeDay } from '@/lib/events';

const EASE = [0.16, 1, 0.3, 1] as const;

export function CountUp({ value, duration = 1100 }: { value: number; duration?: number }) {
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

  return <span ref={ref} className="tabular-nums">{reduce ? value : n}</span>;
}

export function TiltCard({ children, className, href, style, onClick }: { children: React.ReactNode; className?: string; href?: string; style?: React.CSSProperties; onClick?: (e: React.MouseEvent<HTMLDivElement>) => void }) {
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

  const motionStyle = reduce ? style : { ...style, rotateX, rotateY, transformPerspective: 1000 };

  const content = (
    <motion.div
      onClick={onClick}
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

export function Ring({ pct, color, size = 46 }: { pct: number; color: string; size?: number }) {
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

export function SectionHead({ title, href, cta }: { title: string; href?: string; cta?: string }) {
  return (
    <div className="flex items-center justify-between mb-3">
      <h2 className="text-[20px] font-black tracking-[-0.04em] text-[#171717]">{title}</h2>
      {cta && href && (
        <Link
          href={href}
          className="flex items-center gap-0.5 rounded-full bg-white px-3 py-1.5 text-xs font-black text-[#FF5A36] shadow-[0_10px_22px_rgba(30,30,30,0.06)] transition-all hover:gap-1.5 active:scale-[0.98]"
        >
          {cta} <ChevronRight className="w-3.5 h-3.5" />
        </Link>
      )}
    </div>
  );
}

export function StickyNote({
  e,
  index,
  activeIndex,
  setActiveIndex,
  total,
  onSelect,
}: {
  e: AcademicEvent;
  index: number;
  activeIndex: number;
  setActiveIndex: (idx: number) => void;
  total: number;
  onSelect?: (event: AcademicEvent) => void;
}) {
  const tone = cascadeTone(e);
  const meta = TYPE_META[e.event_type];
  const position = (index - activeIndex + total) % total;
  const rot = position === 0 ? -2 : position % 2 === 0 ? 4 : -5;
  const offsetY = position * 18;
  const scale = position === 0 ? 1 : 1 - position * 0.05;
  const z = total - position;

  const isInitial = useRef(true);
  useEffect(() => { isInitial.current = false; }, []);

  const transition = isInitial.current
    ? { duration: 0.4, ease: EASE }
    : { type: 'spring' as const, stiffness: 220, damping: 26 };

  const handleClick = (ev: React.MouseEvent) => {
    if (position !== 0) { 
      ev.preventDefault(); 
      setActiveIndex(index); 
    } else if (onSelect) {
      ev.preventDefault();
      onSelect(e);
    }
  };

  const Wrapper = onSelect ? 'a' : Link;
  const hrefProps = onSelect ? { href: "#" } : { href: "/updates" };

  return (
    <Wrapper
      {...hrefProps}
      onClick={handleClick}
      className="absolute inset-x-0 mx-auto block focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#FF5A36] rounded-[28px]"
      style={{ zIndex: z, width: 'min(100%, 440px)' }}
      aria-label={`${meta.tag}: ${e.title}`}
    >
      <motion.div
        initial={{ opacity: 0, y: offsetY + 12, rotate: rot, scale }}
        animate={{ opacity: 1, y: offsetY, rotate: rot, scale }}
        transition={transition}
        whileHover={{ y: offsetY - (position === 0 ? 6 : 3), scale: scale * (position === 0 ? 1.02 : 1.01) }}
        className="relative mx-auto w-full rounded-[28px] p-5 shadow-[0_24px_50px_rgba(30,30,30,0.12),inset_0_1px_0_rgba(255,255,255,0.6)] cursor-pointer"
        style={{ background: tone.bg }}
      >
        <span className="absolute -top-2 left-1/2 h-4 w-16 -translate-x-1/2 rounded-[3px] bg-white/55 shadow-sm" aria-hidden />
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
        <div className="mt-2 flex items-center justify-between gap-2">
          <p className="text-xs font-bold text-[#1E1B2E]/70 shrink-0">{relativeDay(e.date_time, e.date_precision)}</p>
          {e.group_name ? (
            <p className="text-[11px] font-semibold text-[#1E1B2E]/60 truncate text-right">
              From {e.group_name}
            </p>
          ) : (
            <p className="text-[11px] font-black uppercase tracking-wide text-[#1E1B2E]/50">{tone.label}</p>
          )}
        </div>
      </motion.div>
    </Wrapper>
  );
}

export function formatRelativeTime(iso?: string): string {
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

export function CoverageBanner({ state, name }: { state: string; name: string }) {
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
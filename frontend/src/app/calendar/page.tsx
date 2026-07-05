'use client';
import React, { useEffect, useMemo, useRef, useState } from 'react';
import { motion } from 'framer-motion';
import { useAppStore } from '@/lib/store';
import type { AcademicEvent } from '@/lib/events';
import { TYPE_META, TYPE_COLOR } from '@/lib/events';
import { ChevronLeft, ChevronRight } from 'lucide-react';

const MONTHS = ['January','February','March','April','May','June','July','August','September','October','November','December'];
const WEEKDAYS = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'];

// Vertical item height — each date row + padding for center alignment
const ITEM_H = 64;

function pad(n: number) { return n < 10 ? `0${n}` : `${n}`; }

function buildDateList(year: number, month: number): { day: number; date: Date; label: string; weekday: string }[] {
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  return Array.from({ length: daysInMonth }, (_, i) => {
    const day = i + 1;
    const date = new Date(year, month, day);
    return {
      day,
      date,
      label: pad(day),
      weekday: WEEKDAYS[date.getDay()],
    };
  });
}

export default function CalendarPage() {
  const { events, fetchEvents } = useAppStore();
  const today = new Date();
  const [year, setYear] = useState(today.getFullYear());
  const [month, setMonth] = useState(today.getMonth());
  const [selected, setSelected] = useState(today.getDate());
  const scrollRef = useRef<HTMLDivElement>(null);
  const isScrollingProgrammatically = useRef(false);

  useEffect(() => {
    fetchEvents({ limit: 100 });
  }, [fetchEvents]);

  const allEvents = useMemo(() => (events as AcademicEvent[]).filter((e) => e.date_time), [events]);

  const agendaByDay = useMemo(() => {
    const map: Record<number, AcademicEvent[]> = {};
    for (const e of allEvents) {
      const d = new Date(e.date_time as string);
      if (d.getFullYear() === year && d.getMonth() === month) {
        const day = d.getDate();
        (map[day] ||= []).push(e);
      }
    }
    for (const k of Object.keys(map)) {
      map[Number(k)].sort((a, b) => new Date(a.date_time as string).getTime() - new Date(b.date_time as string).getTime());
    }
    return map;
  }, [allEvents, year, month]);

  const dateList = useMemo(() => buildDateList(year, month), [year, month]);

  const prevMonth = () => { if (month === 0) { setMonth(11); setYear(y => y - 1); } else setMonth(m => m - 1); };
  const nextMonth = () => { if (month === 11) { setMonth(0); setYear(y => y + 1); } else setMonth(m => m + 1); };

  const selectedItems = agendaByDay[selected] || [];
  const ordinal = [1, 21, 31].includes(selected) ? 'st' : [2, 22].includes(selected) ? 'nd' : [3, 23].includes(selected) ? 'rd' : 'th';

  // Center the selected date in the wheel whenever it or the month changes.
  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    isScrollingProgrammatically.current = true;
    el.scrollTo({ top: (selected - 1) * ITEM_H, behavior: 'smooth' });
    // Reset flag after scroll animation settles
    const t = setTimeout(() => { isScrollingProgrammatically.current = false; }, 400);
    return () => clearTimeout(t);
  }, [selected, year, month]);

  // Snap-select on scroll end
  const scrollTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);
  const handleScroll = () => {
    if (isScrollingProgrammatically.current) return;
    if (scrollTimeout.current) clearTimeout(scrollTimeout.current);
    scrollTimeout.current = setTimeout(() => {
      const el = scrollRef.current;
      if (!el) return;
      const idx = Math.round(el.scrollTop / ITEM_H) + 1;
      if (idx !== selected && idx >= 1 && idx <= dateList.length) {
        setSelected(idx);
      }
    }, 80);
  };

  return (
    <div className="app-page pb-24">
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="mb-4">
        <h1 className="page-title">Calendar <span className="orange-highlight">view</span></h1>
        <p className="page-copy mt-2">Your academic schedule at a glance.</p>
      </motion.div>

      {/* Month nav */}
      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex items-center justify-between mb-4">
        <button onClick={prevMonth} className="w-9 h-9 flex items-center justify-center rounded-[18px] bg-[#F4F3EF] hover:bg-white transition-colors clay-icon" aria-label="Previous month">
          <ChevronLeft className="w-4 h-4 text-[var(--text-2)]" />
        </button>
        <h2 className="text-[20px] font-black tracking-[-0.04em] text-[var(--text-1)]">{MONTHS[month]} {year}</h2>
        <button onClick={nextMonth} className="w-9 h-9 flex items-center justify-center rounded-[18px] bg-[#F4F3EF] hover:bg-white transition-colors clay-icon" aria-label="Next month">
          <ChevronRight className="w-4 h-4 text-[var(--text-2)]" />
        </button>
      </motion.div>

      {/* Wheel + Agenda */}
      <div className="flex gap-3 sm:gap-4 items-start overflow-hidden">
        {/* ── Date Wheel ── */}
        <div className="relative w-[88px] shrink-0 overflow-hidden rounded-[24px] bg-white/40 backdrop-blur-md border border-[var(--border-soft)]" style={{ height: ITEM_H * 5 }}>
          {/* Glass fade mask top */}
          <div className="pointer-events-none absolute inset-x-0 top-0 z-10 h-1/2 bg-gradient-to-b from-[#FBFBFA] via-[#FBFBFA]/70 to-transparent" />
          {/* Glass fade mask bottom */}
          <div className="pointer-events-none absolute inset-x-0 bottom-0 z-10 h-1/2 bg-gradient-to-t from-[#FBFBFA] via-[#FBFBFA]/70 to-transparent" />
          {/* Center selection indicator */}
          <div className="pointer-events-none absolute inset-x-2 top-1/2 -translate-y-1/2 z-20 rounded-[16px] bg-[var(--primary)]/8 border border-[var(--primary)]/15" style={{ height: ITEM_H }} />

          <div
            ref={scrollRef}
            onScroll={handleScroll}
            className="h-full overflow-y-auto snap-y snap-mandatory no-scrollbar"
            style={{ scrollSnapType: 'y mandatory', paddingTop: ITEM_H * 2, paddingBottom: ITEM_H * 2 }}
          >
            {dateList.map((d) => {
              const isSel = d.day === selected;
              const isToday = d.day === today.getDate() && month === today.getMonth() && year === today.getFullYear();
              const hasEvents = (agendaByDay[d.day]?.length ?? 0) > 0;
              return (
                <button
                  key={d.day}
                  onClick={() => setSelected(d.day)}
                  className="relative snap-center w-full flex flex-col items-center justify-center transition-all duration-200"
                  style={{ height: ITEM_H }}
                >
                  <span
                    className={`font-black tabular-nums leading-none transition-all duration-200 ${
                      isSel ? 'text-[28px] text-[var(--text-1)]' : 'text-[20px] text-[var(--text-3)]'
                    }`}
                  >
                    {d.label}
                  </span>
                  <span
                    className={`text-[9px] font-black uppercase tracking-wider transition-all duration-200 ${
                      isSel ? 'text-[var(--primary)] mt-1 opacity-100' : 'text-[var(--text-3)]/50 mt-0.5 opacity-60'
                    }`}
                  >
                    {isSel ? d.weekday : isToday ? 'Today' : ''}
                  </span>
                  {hasEvents && (
                    <>
                      <div
                        className={`absolute right-2 top-1/2 -translate-y-1/2 min-w-[20px] h-5 px-1.5 rounded-full flex items-center justify-center text-[10px] font-black shadow-sm transition-all duration-200 ${
                          isSel
                            ? 'bg-[var(--primary)] text-white'
                            : 'bg-[#FFF1E8] text-[#C25A1A] border border-[#F0C7A8]'
                        }`}
                      >
                        {agendaByDay[d.day].length}
                      </div>

                      <div className="absolute bottom-2 flex gap-1">
                        {agendaByDay[d.day].slice(0, 3).map((e, j) => (
                          <div
                            key={j}
                            className="w-1.5 h-1.5 rounded-full shadow-sm"
                            style={{ background: isSel ? 'rgba(255,255,255,0.85)' : TYPE_COLOR[e.event_type] }}
                          />
                        ))}
                      </div>
                    </>
                  )}
                </button>
              );
            })}
          </div>
        </div>

        {/* ── Agenda for selected date ── */}
        <motion.div
          key={selected}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
          className="flex-1 min-w-0 pt-4 sm:pt-[128px]"
        >
          <h3 className="text-[20px] font-black tracking-[-0.04em] mb-3 text-[var(--text-1)]">
            {MONTHS[month]} {selected}{ordinal}
          </h3>

          {selectedItems.length === 0 ? (
            <div className="clay-card p-6 text-center">
              <p className="text-sm font-bold text-[var(--text-3)]">No events scheduled for this day.</p>
            </div>
          ) : (
            <div className="space-y-3">
              {selectedItems.map((item, j) => {
                const color = TYPE_COLOR[item.event_type];
                const meta = TYPE_META[item.event_type];
                const time = new Date(item.date_time as string).toLocaleTimeString('en-US', { timeZone: 'Africa/Lagos', hour: '2-digit', minute: '2-digit', hour12: false });
                const isMidnight = time === '12:00 AM' || time === '00:00';
                return (
                  <div key={j} className="clay-card flex items-center gap-3.5 p-4 sm:p-5 transition-transform hover:-translate-y-0.5">
                    <div className="w-1.5 h-12 rounded-full shrink-0" style={{ background: color }} />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm sm:text-[15px] font-black tracking-[-0.01em] text-[var(--text-1)] truncate">{item.title}</p>
                      <p className="text-xs text-[var(--text-3)] font-semibold mt-1 flex items-center gap-1.5">
                        {item.course_code ? `${item.course_code} · ` : ''}
                        {isMidnight ? 'All day' : time}
                        {item.venue ? ` · ${item.venue}` : ''}
                      </p>
                    </div>
                    <span className="badge shrink-0 flex items-center gap-1" style={{ background: color + '18', color, borderColor: 'transparent' }}>
                      <meta.icon className="w-3 h-3" />
                      {meta.tag}
                    </span>
                  </div>
                );
              })}
            </div>
          )}
        </motion.div>
      </div>
    </div>
  );
}

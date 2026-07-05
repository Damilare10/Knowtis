'use client';

import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Smartphone, Wifi, Flame, ChevronRight } from 'lucide-react';

export default function AndroidWidgetPreview({ widgetData, isLoading }: { widgetData: any; isLoading: boolean }) {
  const [activeWidget, setActiveWidget] = useState<'brief' | 'cascade'>('brief');
  const [activeCardIndex, setActiveCardIndex] = useState(0);
  const [phoneTime, setPhoneTime] = useState('14:00');

  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      const hrs = String(now.getHours()).padStart(2, '0');
      const mins = String(now.getMinutes()).padStart(2, '0');
      setPhoneTime(`${hrs}:${mins}`);
    };
    updateTime();
    const interval = setInterval(updateTime, 60000);
    return () => clearInterval(interval);
  }, []);

  const brief = widgetData?.daily_brief;
  const cascade = widgetData?.cascade_events ?? [];

  const nextCard = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (cascade.length > 0) {
      setActiveCardIndex((prev) => (prev + 1) % cascade.length);
    }
  };

  return (
    <div className="space-y-4 w-full">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-full bg-[#FF5A36]/10 flex items-center justify-center">
            <Smartphone className="w-4 h-4 text-[#FF5A36]" />
          </div>
          <div className="text-left">
            <h3 className="text-sm font-black text-[#171717]">Android Widget Preview</h3>
            <p className="text-[11px] font-semibold text-[#74736D]">Ambient class updates on your home screen</p>
          </div>
        </div>
        <div className="flex bg-[var(--surface-2)] rounded-full p-1 border border-[var(--border)] shadow-sm w-fit self-start sm:self-auto">
          <button
            onClick={() => setActiveWidget('brief')}
            className={`px-3 py-1 rounded-full text-[11px] font-black tracking-[-0.01em] transition-all ${
              activeWidget === 'brief' ? 'bg-[#FF5A36] text-white shadow-sm' : 'text-[#686862]'
            }`}
          >
            Daily Brief (2x2)
          </button>
          <button
            onClick={() => setActiveWidget('cascade')}
            className={`px-3 py-1 rounded-full text-[11px] font-black tracking-[-0.01em] transition-all ${
              activeWidget === 'cascade' ? 'bg-[#FF5A36] text-white shadow-sm' : 'text-[#686862]'
            }`}
          >
            Cascade (4x2)
          </button>
        </div>
      </div>

      {/* Phone chassis with double-bezel concentric curves */}
      <div className="relative mx-auto w-full max-w-[280px] rounded-[44px] bg-[#171717] p-3 shadow-[0_24px_50px_rgba(0,0,0,0.18),inset_0_2px_3px_rgba(255,255,255,0.12)] border border-[#262626] overflow-hidden">
        {/* Concentric Screen Border */}
        <div className="relative aspect-[9/18.5] w-full rounded-[34px] bg-[#0c0c0e] overflow-hidden flex flex-col justify-between p-4 select-none">
          {/* Custom Mesh Gradient Wallpaper */}
          <div className="absolute inset-0 z-0 bg-gradient-to-tr from-[#050508] via-[#120f26] to-[#0c0c0e]">
            <div className="absolute top-1/4 left-1/4 w-36 h-36 rounded-full bg-[#FF5A36]/10 blur-[40px] animate-pulse" />
            <div className="absolute bottom-1/3 right-1/4 w-32 h-32 rounded-full bg-[#4285F4]/08 blur-[35px]" />
          </div>

          {/* Status Bar */}
          <div className="relative z-10 flex items-center justify-between text-white/90 text-[10px] font-bold px-1 select-none">
            <span>{phoneTime}</span>
            <div className="flex items-center gap-1.5">
              <Wifi className="w-3.5 h-3.5 text-white/80" />
              <div className="flex items-center gap-0.5 border border-white/50 rounded-sm px-0.5 py-[1px] h-3 w-5">
                <div className="bg-white h-full w-3 rounded-[1px]" />
              </div>
            </div>
          </div>

          {/* Widget Placement Area */}
          <div className="relative z-10 flex-1 flex flex-col items-center justify-center py-6">
            {activeWidget === 'brief' ? (
              /* 2x2 Daily Brief Widget */
              <motion.div
                key="brief-widget"
                initial={{ opacity: 0, scale: 0.94 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.94 }}
                transition={{ type: 'spring', stiffness: 350, damping: 25 }}
                className="w-[145px] h-[145px] rounded-[24px] border border-white/10 bg-black/45 backdrop-blur-xl p-3 flex flex-col justify-between shadow-[0_12px_24px_rgba(0,0,0,0.5),inset_0_1px_1px_rgba(255,255,255,0.12)]"
              >
                <div className="flex items-center justify-between">
                  <span className="text-[9px] font-black uppercase tracking-[0.06em] text-[#FF5A36]">Daily Brief</span>
                  <div className="w-1.5 h-1.5 rounded-full bg-[#32B87B] animate-ping" />
                </div>
                
                <div className="my-1.5 text-left">
                  <h3 className="text-[26px] font-black leading-none text-white tracking-tight">
                    {isLoading ? '-' : (brief?.deadlines_today ?? 0) + (brief?.schedule_changes_today ?? 0)}
                  </h3>
                  <p className="text-[9px] font-bold text-white/50 leading-tight mt-0.5">Updates today</p>
                </div>

                <div className="border-t border-white/10 pt-2 flex flex-col gap-0.5 text-left">
                  <div className="flex items-center justify-between text-[9px] font-bold text-white/80">
                    <span>Deadlines</span>
                    <span className="text-white font-black">{isLoading ? '-' : brief?.deadlines_today ?? 0}</span>
                  </div>
                  <div className="flex items-center justify-between text-[9px] font-bold text-white/80">
                    <span>Changes</span>
                    <span className="text-white font-black">{isLoading ? '-' : brief?.schedule_changes_today ?? 0}</span>
                  </div>
                </div>
              </motion.div>
            ) : (
              /* 4x2 Cascade Widget */
              <motion.div
                key="cascade-widget"
                initial={{ opacity: 0, scale: 0.94 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.94 }}
                transition={{ type: 'spring', stiffness: 350, damping: 25 }}
                className="w-full rounded-[24px] border border-white/10 bg-black/45 backdrop-blur-xl p-3 flex flex-col justify-between shadow-[0_12px_24px_rgba(0,0,0,0.5),inset_0_1px_1px_rgba(255,255,255,0.12)] min-h-[145px]"
              >
                <div className="flex items-center justify-between border-b border-white/10 pb-1.5 mb-2">
                  <div className="flex items-center gap-1.5">
                    <div className="w-3 h-3 rounded-full bg-[#FF5A36] flex items-center justify-center">
                      <Flame className="w-2 h-2 text-white" />
                    </div>
                    <span className="text-[9px] font-black uppercase tracking-[0.08em] text-white">Cascade</span>
                  </div>
                  <span className="text-[8px] font-black text-white/40 uppercase">
                    {cascade.length > 0 ? `${activeCardIndex + 1} of ${cascade.length}` : 'Empty'}
                  </span>
                </div>

                <div className="flex-1 flex flex-col justify-center relative min-h-[64px] text-left">
                  {isLoading ? (
                    <div className="text-center py-2 text-white/30 text-xs font-bold">Syncing...</div>
                  ) : cascade.length === 0 ? (
                    <div className="text-center py-2 text-white/40 text-[10px] font-bold">No upcoming deadlines</div>
                  ) : (
                    <div className="relative w-full h-[60px]" onClick={nextCard}>
                      {cascade.map((item: any, idx: number) => {
                        if (idx !== activeCardIndex) return null;
                        const eventDate = item.date_time ? new Date(item.date_time) : null;
                        const dateStr = eventDate ? eventDate.toLocaleDateString('en-US', { timeZone: 'Africa/Lagos', weekday: 'short', day: 'numeric' }) : 'Unscheduled';
                        
                        return (
                          <motion.div
                            key={item.id}
                            initial={{ opacity: 0, x: 20 }}
                            animate={{ opacity: 1, x: 0 }}
                            exit={{ opacity: 0, x: -20 }}
                            className="absolute inset-0 flex flex-col justify-between cursor-pointer"
                          >
                            <div>
                              <div className="flex items-center gap-1.5">
                                <span className="text-[8px] font-black px-1.5 py-0.5 rounded-sm bg-[#FF5A36]/20 text-[#FF5A36] uppercase tracking-wide">
                                  {item.event_type}
                                </span>
                                {item.course_code && (
                                  <span className="text-[9px] font-bold text-white/80">{item.course_code}</span>
                                )}
                              </div>
                              <h4 className="text-xs font-black text-white leading-tight mt-1 line-clamp-1">
                                {item.title}
                              </h4>
                            </div>
                            <div className="flex items-center justify-between text-[9px] text-white/50 font-bold border-t border-white/5 pt-1">
                              <span>{dateStr}</span>
                              <span className="text-white/70 truncate max-w-[60px]">{item.venue || 'No venue'}</span>
                            </div>
                          </motion.div>
                        );
                      })}
                    </div>
                  )}
                </div>

                {cascade.length > 1 && (
                  <button
                    onClick={nextCard}
                    className="mt-2 w-full py-1 rounded-lg bg-white/10 hover:bg-white/20 active:scale-[0.98] text-[9px] font-black text-white transition-all flex items-center justify-center gap-1 shadow-sm"
                  >
                    Next Update <ChevronRight className="w-2.5 h-2.5" />
                  </button>
                )}
              </motion.div>
            )}
          </div>

          {/* Navigation Pill */}
          <div className="relative z-10 mx-auto h-1 w-20 rounded-full bg-white/40 mb-1" />
        </div>
      </div>
    </div>
  );
}

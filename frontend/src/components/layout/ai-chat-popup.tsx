'use client';

import React, { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { AnimatePresence, motion } from 'framer-motion';
import { useAppStore } from '@/lib/store';
import type { ChatMessage } from '@/lib/api';
import { Sparkles, Send, BookOpen, Clock, FileText, Calendar, ArrowRight, User, X } from 'lucide-react';
import { usePathname } from 'next/navigation';

const SUGGESTED = [
  { icon: FileText, text: 'What assignments are due this week?' },
  { icon: Calendar, text: 'Summarise my exam schedule' },
  { icon: Clock, text: 'What deadlines do I have tomorrow?' },
  { icon: BookOpen, text: 'Are there any class cancellations?' },
];

function startOfDay(d: Date): number {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: "Africa/Lagos",
    year: "numeric", month: "numeric", day: "numeric",
  }).formatToParts(d);
  const get = (t: string) => Number(parts.find((p) => p.type === t)?.value);
  return new Date(get("year"), get("month") - 1, get("day"), 0, 0, 0, 0).getTime();
}

function formatDayChip(day: string): string {
  if (!day) return '';
  const lower = day.trim().toLowerCase();
  if (lower === 'today' || lower === 'yesterday') return day.trim();

  const d = new Date(day);
  if (!isNaN(d.getTime())) {
    const diff = Math.round((startOfDay(d) - startOfDay(new Date())) / 86_400_000);
    if (diff === 0) return 'Today';
    if (diff === -1) return 'Yesterday';
    return d.toLocaleDateString('en-US', { timeZone: 'Africa/Lagos', weekday: 'short', month: 'short', day: 'numeric' });
  }
  return day;
}

type Row =
  | { kind: 'divider'; key: string; label: string }
  | { kind: 'msg'; key: string; msg: ChatMessage };

function buildRows(messages: ChatMessage[]): Row[] {
  const rows: Row[] = [];
  let lastLabel = '';
  messages.forEach((msg, i) => {
    const label = formatDayChip(msg.day);
    if (label !== lastLabel) {
      rows.push({ kind: 'divider', key: `d-${i}-${label || 'none'}`, label });
      lastLabel = label;
    }
    rows.push({ kind: 'msg', key: msg.id ?? `m-${i}`, msg });
  });
  return rows;
}

function renderInline(line: string) {
  const parts = line.split(/(\*\*.+?\*\*)/g);
  return parts.map((part, index) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={index}>{part.slice(2, -2)}</strong>;
    }
    return <React.Fragment key={index}>{part}</React.Fragment>;
  });
}

function renderAI(text: string) {
  return text.split('\n').map((line, i) => {
    const listItem = line.startsWith('-');
    const content = listItem ? line.slice(1).trim() : line;
    return (
      <p key={i} className={`text-sm leading-relaxed ${listItem ? 'pl-1 flex items-start gap-1.5' : ''}`}>
        {listItem && <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-[var(--text-3)]" />}
        {renderInline(content)}
      </p>
    );
  });
}

export default function AIChatPopup() {
  const isOpen = useAppStore((s) => s.aiPopupOpen);
  const setIsOpen = useAppStore((s) => s.setAiPopupOpen);

  const aiMessages = useAppStore((s) => s.aiMessages);
  const aiHistoryLoading = useAppStore((s) => s.aiHistoryLoading);
  const aiSending = useAppStore((s) => s.aiSending);
  const aiChatError = useAppStore((s) => s.aiChatError);
  const fetchAIHistory = useAppStore((s) => s.fetchAIHistory);
  const sendAIMessage = useAppStore((s) => s.sendAIMessage);
  const clearAIChatError = useAppStore((s) => s.clearAIChatError);

  const [input, setInput] = useState('');
  const [mounted, setMounted] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const pathname = usePathname();

  // Handle portal mounting
  useEffect(() => {
    setMounted(true);
  }, []);

  // Fetch AI History once when opened
  useEffect(() => {
    if (isOpen) {
      fetchAIHistory();
    }
  }, [isOpen, fetchAIHistory]);

  // Keep latest message in view
  useEffect(() => {
    if (isOpen) {
      setTimeout(() => {
        bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
      }, 100);
    }
  }, [isOpen, aiMessages, aiSending]);

  // Close popup automatically on page navigation
  useEffect(() => {
    setIsOpen(false);
  }, [pathname, setIsOpen]);

  const send = (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || aiSending) return;
    setInput('');
    sendAIMessage(trimmed);
  };

  if (!mounted) return null;

  const rows = buildRows(aiMessages);
  const isEmpty = aiMessages.length === 0 && !aiHistoryLoading;

  return createPortal(
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop Overlay */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 0.4 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.3 }}
            onClick={() => setIsOpen(false)}
            className="fixed inset-0 bg-[#171717] z-[140] backdrop-blur-sm cursor-pointer"
          />

          {/* Assistant Panel Drawer */}
          <motion.div
            initial={{ 
              x: typeof window !== 'undefined' && window.innerWidth >= 1024 ? '110%' : 0,
              y: typeof window !== 'undefined' && window.innerWidth < 1024 ? '110%' : 0,
              opacity: 0.9
            }}
            animate={{ x: 0, y: 0, opacity: 1 }}
            exit={{ 
              x: typeof window !== 'undefined' && window.innerWidth >= 1024 ? '110%' : 0,
              y: typeof window !== 'undefined' && window.innerWidth < 1024 ? '110%' : 0,
              opacity: 0.9
            }}
            transition={{ type: 'spring', stiffness: 380, damping: 35 }}
            className="fixed z-[150] flex flex-col overflow-hidden bg-white/80 backdrop-blur-2xl border border-white/60 shadow-2xl
              /* Mobile Positioning */
              bottom-4 left-4 right-4 top-[14dvh] rounded-[2rem]
              /* Desktop Positioning */
              lg:top-4 lg:bottom-4 lg:right-4 lg:left-auto lg:w-[460px]"
          >
            {/* Header */}
            <div className="p-5 border-b border-[#E9E9E6]/50 bg-white/40 flex items-start gap-3 shrink-0">
              <div className="w-10 h-10 rounded-[14px] bg-[#FFF0EB] flex items-center justify-center rotate-[-3deg] shadow-sm shrink-0">
                <Sparkles className="w-5 h-5 text-[#FF5A36]" />
              </div>
              <div className="flex-1 min-w-0">
                <h3 className="text-[17px] font-black tracking-tight text-[#171717]">Knowtis Assistant</h3>
                <p className="text-[11px] font-bold text-[#74736D] uppercase tracking-wider mt-0.5">Ask anything about your deadlines</p>
              </div>
              <button
                type="button"
                onClick={() => setIsOpen(false)}
                aria-label="Close Assistant"
                className="w-8 h-8 rounded-full bg-white border border-[#E9E9E6] flex items-center justify-center shrink-0 shadow-sm hover:bg-[#FBFBFA] active:scale-95 transition-all"
              >
                <X className="w-4 h-4 text-[#74736D]" />
              </button>
            </div>

            {/* Chat Conversation Area */}
            <div className="flex-1 overflow-y-auto p-5 space-y-4 min-h-0 bg-white/20">
              {/* Loading State */}
              {aiHistoryLoading && (
                <div className="space-y-4">
                  {[0, 1, 2].map((i) => (
                    <div key={i} className={`flex gap-2.5 ${i % 2 ? 'flex-row-reverse' : ''}`}>
                      <div className="w-8 h-8 rounded-[18px] skeleton shrink-0" />
                      <div className="max-w-[80%] space-y-2">
                        <div className="skeleton h-3 w-44 rounded-full" />
                        <div className="skeleton h-3 w-32 rounded-full" />
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* Empty state: suggested questions */}
              {isEmpty && (
                <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.1 }}>
                  <p className="text-[11px] font-black uppercase tracking-wider text-[#A3A29C] mb-3">Suggested queries</p>
                  <div className="space-y-2">
                    {SUGGESTED.map((s, i) => (
                      <button
                        key={i}
                        onClick={() => send(s.text)}
                        className="w-full flex items-center gap-3 p-3.5 text-left bg-white/70 hover:bg-white border border-[#E9E9E6]/60 rounded-2xl hover:-translate-y-0.5 transition-all duration-200 shadow-sm"
                      >
                        <div className="w-8 h-8 rounded-xl bg-[#FFF0EB] flex items-center justify-center shrink-0">
                          <s.icon className="w-4 h-4 text-[#FF5A36]" />
                        </div>
                        <p className="text-[13px] font-bold text-[#171717] flex-1">{s.text}</p>
                        <ArrowRight className="w-3.5 h-3.5 text-[#A3A29C] shrink-0" />
                      </button>
                    ))}
                  </div>
                </motion.div>
              )}

              {/* Conversation list */}
              <AnimatePresence initial={false}>
                {rows.map((row) =>
                  row.kind === 'divider' ? (
                    <div key={row.key} className="sticky top-2 z-10 flex justify-center">
                      <span className="px-3 py-1 rounded-full bg-white/90 backdrop-blur border border-[#E9E9E6] text-[10px] font-black uppercase text-[#74736D] shadow-sm">
                        {row.label}
                      </span>
                    </div>
                  ) : (
                    <MessageBubble key={row.key} msg={row.msg} />
                  )
                )}
              </AnimatePresence>

              {/* Typing indicator */}
              {aiSending && (
                <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex gap-2.5">
                  <div className="w-8 h-8 rounded-full bg-[#FF5A36] flex items-center justify-center shrink-0 shadow-md">
                    <Sparkles className="w-3.5 h-3.5 text-white" />
                  </div>
                  <div className="bg-white border border-[#E9E9E6]/50 rounded-2xl p-4 flex items-center gap-1.5 shadow-sm">
                    {[0, 1, 2].map((j) => (
                      <div key={j} className="w-1.5 h-1.5 rounded-full bg-[#FF5A36] animate-dot" style={{ animationDelay: `${j * 0.2}s` }} />
                    ))}
                  </div>
                </motion.div>
              )}

              <div ref={bottomRef} />
            </div>

            {/* Error toast */}
            {aiChatError && (
              <div className="mx-5 mb-2 flex items-center gap-2 px-3.5 py-2.5 rounded-2xl bg-red-50 border border-red-100 text-red-600 text-xs font-semibold shrink-0">
                <span className="flex-1">{aiChatError}</span>
                <button onClick={() => { clearAIChatError(); fetchAIHistory(); }} className="font-black uppercase tracking-wider text-[10px] hover:underline">
                  Retry
                </button>
              </div>
            )}

            {/* Input Bar */}
            <div className="p-4 bg-white/40 border-t border-[#E9E9E6]/50 shrink-0">
              <form
                onSubmit={(e) => { e.preventDefault(); send(input); }}
                className="bg-white border border-[#E9E9E6] rounded-2xl flex items-center gap-2 p-1.5 shadow-sm"
              >
                <label htmlFor="ai-popup-question" className="sr-only">Ask Knowtis AI</label>
                <input
                  id="ai-popup-question"
                  type="text"
                  autoComplete="off"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder="Ask about deadlines, exams, updates..."
                  disabled={aiSending}
                  className="flex-1 bg-transparent outline-none text-xs font-bold text-[#171717] placeholder:text-[#A3A29C] px-3 py-2 disabled:opacity-50"
                />
                <button
                  type="submit"
                  aria-label="Send question"
                  disabled={!input.trim() || aiSending}
                  className="w-9 h-9 rounded-xl bg-[#171717] hover:bg-[#2c2c2c] text-white flex items-center justify-center shrink-0 disabled:opacity-40 transition-all active:scale-95 shadow-sm"
                >
                  <Send className="w-3.5 h-3.5" />
                </button>
              </form>
            </div>

          </motion.div>
        </>
      )}
    </AnimatePresence>,
    document.body
  );
}

interface MessageBubbleProps {
  msg: ChatMessage;
}

function MessageBubble({ msg }: MessageBubbleProps) {
  const isUser = msg.role === 'user';
  const isBrief = msg.role === 'brief';

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className={`flex gap-2.5 ${isUser ? 'flex-row-reverse' : ''}`}
    >
      <div
        className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 ${
          isUser
            ? 'bg-[#F4F3EF] border border-[#E9E9E6]'
            : 'bg-[#FF5A36] text-white shadow-md'
        }`}
      >
        {isUser ? (
          <User className="w-3.5 h-3.5 text-[#74736D]" />
        ) : (
          <Sparkles className="w-3.5 h-3.5 text-white" />
        )}
      </div>

      <div
        className={`max-w-[80%] p-3.5 rounded-2xl space-y-1.5 text-xs font-semibold ${
          isUser
            ? 'bg-[#171717] text-white rounded-tr-sm shadow-sm'
            : isBrief
              ? 'bg-[#FFF0EB] border border-[#FFD8CD] rounded-tl-sm text-[#FF5A36]'
              : 'bg-white border border-[#E9E9E6]/50 rounded-tl-sm text-[#171717] shadow-sm'
        }`}
      >
        {isBrief && (
          <div className="flex items-center gap-1.5 mb-1.5">
            <Calendar className="w-3 h-3 text-[#FF5A36]" />
            <span className="text-[9px] font-black uppercase tracking-wider text-[#FF5A36]">Daily brief</span>
          </div>
        )}
        {isUser ? (
          <p className="leading-relaxed">{msg.content}</p>
        ) : (
          renderAI(msg.content)
        )}
      </div>
    </motion.div>
  );
}

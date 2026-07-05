"use client";

import Link from 'next/link';
import { motion, AnimatePresence } from 'framer-motion';
import { useState } from 'react';
import {
  ArrowRight,
  Bell,
  CalendarDays,
  CheckCircle2,
  Clock3,
  FileText,
  MessageCircle,
  ScanLine,
  Sparkles,
  Star,
  Check,
  ChevronDown,
  Users,
  Zap,
  BookOpen,
  GraduationCap,
  Laptop,
  Search,
  VolumeX,
  Image as ImageIcon,
} from 'lucide-react';
import AppLogo from '@/components/ui/app-logo';

const updates = [
  { tag: 'ELE401', title: 'Technical report submission', time: 'Tomorrow', tone: 'urgent' },
  { tag: 'REG', title: 'Course registration closes', time: 'Friday', tone: 'soon' },
  { tag: 'CSC301', title: 'Exam timetable released', time: 'Today', tone: 'info' },
];

const benefits = [
  {
    icon: ScanLine,
    title: 'Scans group noise',
    copy: 'Knowtis turns busy class chats into a short briefing of deadlines, events, and alerts.',
  },
  {
    icon: CalendarDays,
    title: 'Builds your calendar',
    copy: 'Detected dates become clean academic events, so your week stops living in screenshots.',
  },
  {
    icon: Sparkles,
    title: 'Explains what matters',
    copy: 'Ask the assistant what changed, what is urgent, and what you should do next.',
  },
];

const applyCases = [
  {
    icon: GraduationCap,
    title: 'Freshmen & New Students',
    copy: 'Hit the ground running. Every orientation, deadline, and lab swap lands on your dashboard from day one.',
  },
  {
    icon: Laptop,
    title: 'Seniors & Project Leads',
    copy: 'Protect deep-work hours. Knowtis keeps your timeline tidy so your final year ships on time.',
  },
  {
    icon: Users,
    title: 'Course Reps',
    copy: 'Be heard on the first read. Your announcements surface where classmates actually look.',
  },
];

const features = [
  { icon: ScanLine, title: 'AI Chat Summaries', desc: 'Catch up on what mattered in seconds — even after hundreds of messages.' },
  { icon: CalendarDays, title: 'Auto-Calendar Sync', desc: 'Deadlines land on your schedule the moment they are detected.' },
  { icon: Bell, title: 'Priority Alerts', desc: 'Notifications only when an academic deadline moves or appears.' },
  { icon: VolumeX, title: 'Smart Silencing', desc: 'Memes, jokes, and small talk stay out of your way in study groups.' },
  { icon: Clock3, title: 'Deadline Tracking', desc: 'Visual countdowns to your most important submissions.' },
  { icon: Search, title: 'Deep Search', desc: 'Find any past announcement or shared link in two taps.' },
];

const testimonials = [
  {
    name: 'Sarah Jenkins',
    role: 'Computer Science Senior',
    content: 'I used to keep screenshots of every deadline because they got lost in WhatsApp. Knowtis just builds my calendar for me. Lifesaver.',
    rating: 5,
  },
  {
    name: 'David Okafor',
    role: 'Engineering Junior',
    content: 'The AI insight is scary good. It literally told me I had an assignment due tomorrow that I had completely forgotten about from a chat 3 days ago.',
    rating: 5,
  },
  {
    name: 'Emily Chen',
    role: 'Course Representative',
    content: 'As a course rep, it\'s so much easier knowing my classmates use this. My important announcements are pulled out from the noise.',
    rating: 5,
  },
];

const faqs = [
  {
    question: "How does Knowtis access my group chats?",
    answer: "You simply forward important chat exports to your Knowtis assistant, or connect it via our secure integrations. We never read your personal DMs, only the groups you explicitly authorize."
  },
  {
    question: "Which platforms are supported?",
    answer: "Currently, we support WhatsApp, Telegram, and Discord group chats, with Slack integration coming soon."
  },
  {
    question: "Is my academic data secure?",
    answer: "Absolutely. We use enterprise-grade encryption. Your chat data is processed only to extract deadlines and events, and we never sell your data or use it for advertising."
  },
  {
    question: "Can I try it for free?",
    answer: "Yes! Our free tier is perfect for most students and allows you to track up to 3 major course groups per semester."
  },
  {
    question: "What if the AI misses a deadline?",
    answer: "Our AI is highly accurate and specifically trained on academic contexts. However, you always have the ability to manually add or edit events in your dashboard."
  }
];

// High-End Agency Motion Variants (Fluid Dynamics)
const fadeUp = {
  hidden: { opacity: 0, y: 60, filter: 'blur(10px)' },
  visible: { 
    opacity: 1, 
    y: 0, 
    filter: 'blur(0px)',
    transition: { 
      duration: 1.2, 
      ease: [0.16, 1, 0.3, 1] as [number, number, number, number] 
    } 
  },
};

const fadeUpScale = {
  hidden: { opacity: 0, y: 40, scale: 0.95, filter: 'blur(8px)' },
  visible: { 
    opacity: 1, 
    y: 0, 
    scale: 1,
    filter: 'blur(0px)',
    transition: { 
      duration: 1.2, 
      ease: [0.16, 1, 0.3, 1] as [number, number, number, number] 
    } 
  },
};

const staggerContainer = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.15,
    },
  },
};

function FAQItem({ question, answer }: { question: string, answer: string }) {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <div className="border-b border-[#F0F0ED] py-6">
      <button 
        onClick={() => setIsOpen(!isOpen)}
        className="flex w-full items-center justify-between text-left focus:outline-none group"
      >
        <h3 className="text-lg sm:text-xl font-bold text-[#171717] group-hover:text-[#FF5A36] transition-colors pr-4">{question}</h3>
        <span className={`grid h-10 w-10 shrink-0 place-items-center rounded-full bg-black/5 transition-transform duration-500 ease-[cubic-bezier(0.16,1,0.3,1)] ${isOpen ? 'rotate-180 bg-[#FFE6DE] text-[#FF5A36]' : ''}`}>
          <ChevronDown className="h-5 w-5" />
        </span>
      </button>
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ height: 0, opacity: 0, filter: 'blur(4px)' }}
            animate={{ height: 'auto', opacity: 1, filter: 'blur(0px)' }}
            exit={{ height: 0, opacity: 0, filter: 'blur(4px)' }}
            transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] as [number, number, number, number] }}
            className="overflow-hidden"
          >
            <p className="pt-5 text-[15px] sm:text-[16px] leading-relaxed text-[#5F5F59] sm:pr-12">
              {answer}
            </p>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export default function LandingPage() {
  return (
    <main className="min-h-dvh overflow-x-hidden bg-[#FDFDFD] text-[#171717] selection:bg-[#FFD8CD] selection:text-[#C83C21]">
      {/* Background Orbs */}
      <div className="pointer-events-none fixed inset-0 z-0" aria-hidden="true">
        <motion.div 
          animate={{ scale: [1, 1.05, 1], opacity: [0.4, 0.6, 0.4] }}
          transition={{ duration: 12, repeat: Infinity, ease: "easeInOut" }}
          className="absolute -left-32 top-0 h-[600px] w-[600px] rounded-full bg-gradient-to-br from-[#D9F1EC] to-transparent blur-[120px]" 
        />
        <motion.div 
          animate={{ scale: [1, 1.1, 1], opacity: [0.3, 0.5, 0.3] }}
          transition={{ duration: 15, repeat: Infinity, ease: "easeInOut", delay: 1 }}
          className="absolute right-[-120px] top-32 h-[500px] w-[500px] rounded-full bg-gradient-to-bl from-[#F6B39F] to-transparent blur-[120px]" 
        />
        <motion.div 
          animate={{ y: [0, -40, 0], opacity: [0.2, 0.3, 0.2] }}
          transition={{ duration: 10, repeat: Infinity, ease: "easeInOut", delay: 2 }}
          className="absolute left-1/3 top-64 h-[400px] w-[400px] rounded-full bg-gradient-to-t from-[#FFE071] to-transparent blur-[100px]" 
        />
      </div>

      {/* 1. Fluid Island Navbar */}
      <nav className="fixed inset-x-0 top-0 z-50 pt-3 sm:pt-6 px-4 pointer-events-none">
        <div className="mx-auto flex w-full max-w-[1000px] items-center justify-between gap-4 sm:gap-6 rounded-full border border-black/5 bg-white/70 px-3.5 py-2 sm:px-4 sm:py-2.5 shadow-[0_8px_32px_rgba(0,0,0,0.04),inset_0_1px_1px_rgba(255,255,255,1)] backdrop-blur-2xl pointer-events-auto transition-transform duration-700 ease-[cubic-bezier(0.16,1,0.3,1)]">
          <Link href="/" className="flex items-center gap-2 sm:gap-3 pl-2 transition-transform hover:scale-105 active:scale-95" aria-label="Knowtis home">
            <div className="relative flex h-8 w-8 items-center justify-center overflow-hidden rounded-[10px] bg-[#171717] text-[#F0EAD6] shadow-[0_4px_12px_rgba(30,30,30,0.12)]">
              <AppLogo className="w-4 h-4" />
            </div>
            <span className="text-[17px] font-black tracking-[-0.04em] hidden sm:block">Knowtis</span>
          </Link>
          <div className="hidden items-center gap-8 text-[13px] font-bold text-[#5F5F59] md:flex">
            <a href="#how" className="transition-colors hover:text-[#171717]">How it works</a>
            <a href="#benefits" className="transition-colors hover:text-[#171717]">Benefits</a>
            <a href="#features" className="transition-colors hover:text-[#171717]">Features</a>
            <a href="#pricing" className="transition-colors hover:text-[#171717]">Pricing</a>
          </div>
          <div className="flex items-center gap-2">
            <Link href="/login" className="hidden text-sm font-bold text-[#5F5F59] transition-colors hover:text-[#171717] sm:block px-4">
              Log in
            </Link>
            <Link href="/register" className="group flex items-center gap-2 rounded-full bg-[#171717] pl-3.5 sm:pl-5 pr-1 py-1 sm:py-1.5 text-[13px] font-bold text-white transition-all active:scale-[0.96]">
              <span className="hidden sm:inline">Get Started</span>
              <span className="sm:hidden">Start</span>
              <span className="grid h-7 w-7 place-items-center rounded-full bg-white/10 transition-all duration-500 ease-[cubic-bezier(0.16,1,0.3,1)] group-hover:scale-110 group-hover:bg-white/20 group-hover:translate-x-0.5 group-hover:-translate-y-[0.5px]">
                <ArrowRight className="h-3.5 w-3.5" />
              </span>
            </Link>
          </div>
        </div>
      </nav>

      <div className="relative z-10 mx-auto mt-20 sm:mt-32 flex w-full max-w-[1180px] flex-col px-5 sm:px-6 lg:px-8">

        {/* 2. Hero Section */}
        <section className="grid lg:min-h-[calc(100dvh-160px)] items-start lg:items-center gap-8 sm:gap-16 pt-4 pb-12 sm:pt-10 sm:pb-20 lg:grid-cols-[0.9fr_1.1fr] lg:gap-20 lg:py-16">
          <motion.div 
            initial="hidden" 
            animate="visible" 
            variants={staggerContainer}
            className="max-w-[620px]"
          >
            <motion.div variants={fadeUp} className="mb-5 sm:mb-8">
              <span className="inline-flex items-center rounded-full border border-black/5 bg-white/60 px-3 py-1.5 sm:px-4 sm:py-2 text-[10px] sm:text-[11px] font-black uppercase tracking-[0.2em] text-[#C83C21] shadow-[0_2px_8px_rgba(0,0,0,0.02),inset_0_1px_0_rgba(255,255,255,1)] backdrop-blur-md">
                <span className="mr-2 h-1.5 w-1.5 rounded-full bg-[#FF5A36] animate-pulse" />
                AI Academic Assistant
              </span>
            </motion.div>
            <motion.h1 variants={fadeUp} className="font-display text-[clamp(38px,8vw,84px)] font-black leading-[0.9] tracking-[-0.05em] text-[#171717]">
              Never miss the <span className="text-transparent bg-clip-text bg-gradient-to-br from-[#FF5A36] to-[#D93A1C]">deadline</span> that matters.
            </motion.h1>
            <motion.p variants={fadeUp} className="mt-5 sm:mt-8 max-w-[520px] text-[16px] sm:text-[19px] font-medium leading-relaxed text-[#5F5F59]">
              Knowtis turns noisy university group chats into deadlines, reminders, and clear academic updates you can actually act on.
            </motion.p>
            <motion.div variants={fadeUp} className="mt-7 sm:mt-12 flex flex-col items-stretch gap-3 sm:flex-row sm:items-center sm:gap-4">
              <Link href="/register" className="group flex min-h-[56px] sm:min-h-[64px] items-center justify-between sm:justify-start gap-4 rounded-full bg-[#FF5A36] pl-8 pr-2 py-2 text-[16px] sm:text-[17px] font-bold text-white shadow-[0_16px_40px_rgba(255,90,54,0.3)] transition-all duration-500 ease-[cubic-bezier(0.16,1,0.3,1)] active:scale-[0.97] hover:shadow-[0_24px_50px_rgba(255,90,54,0.4)]">
                Start for Free
                <span className="grid h-10 w-10 sm:h-12 sm:w-12 place-items-center rounded-full bg-white/20 transition-all duration-500 ease-[cubic-bezier(0.16,1,0.3,1)] group-hover:scale-105 group-hover:bg-white/30 group-hover:translate-x-1 group-hover:-translate-y-[1px]">
                  <ArrowRight className="h-4 w-4 sm:h-5 sm:w-5" />
                </span>
              </Link>
              <Link href="/login" className="group flex min-h-[56px] sm:min-h-[64px] items-center justify-center gap-1.5 rounded-full px-8 text-[15px] sm:text-[16px] font-bold text-[#5F5F59] transition-colors hover:text-[#171717]">
                See product demo
                <ArrowRight className="h-3.5 w-3.5 opacity-0 -translate-x-1 transition-all duration-300 group-hover:opacity-100 group-hover:translate-x-0" />
              </Link>
            </motion.div>
          </motion.div>

          {/* Hero Image/Demo Area - Enhanced */}
          <motion.div 
            initial="hidden"
            animate="visible"
            variants={fadeUpScale}
            className="relative mx-auto w-full max-w-[600px] lg:mr-0"
          >
            {/* Double-Bezel Main Mockup */}
            <div className="rounded-[2rem] sm:rounded-[3rem] bg-white/20 p-1.5 sm:p-2 border border-white/40 shadow-[0_40px_100px_rgba(0,0,0,0.06),inset_0_1px_0_rgba(255,255,255,1)] backdrop-blur-3xl">
              <div className="rounded-[calc(2rem-0.5rem)] sm:rounded-[calc(3rem-0.5rem)] border border-black/5 bg-white/90 p-4 sm:p-8 shadow-[inset_0_1px_1px_rgba(255,255,255,1)]">
                <div className="mb-6 sm:mb-8 flex items-center justify-between">
                  <div>
                    <p className="text-[10px] sm:text-[11px] font-black uppercase tracking-[0.2em] text-[#A3A29C]">Today</p>
                    <h2 className="mt-1 text-2xl sm:text-3xl font-black tracking-[-0.05em]">Your Briefing</h2>
                  </div>
                  <div className="grid h-12 w-12 sm:h-16 sm:w-16 place-items-center rounded-[1rem] sm:rounded-[1.5rem] bg-gradient-to-b from-[#FF6A49] to-[#FF4B24] text-white shadow-[0_16px_34px_rgba(255,90,54,0.3),inset_0_1px_1px_rgba(255,255,255,0.4)]">
                    <FileText className="h-6 w-6 sm:h-7 sm:w-7" />
                  </div>
                </div>

                <div className="space-y-3 sm:space-y-4">
                  {updates.map((item) => (
                    <div 
                      key={item.title} 
                      className="group flex items-center gap-3 sm:gap-4 rounded-[1rem] sm:rounded-[1.5rem] border border-black/5 bg-[#FDFDFD] p-3 sm:p-4 transition-all duration-500 ease-[cubic-bezier(0.16,1,0.3,1)] hover:border-transparent hover:bg-white hover:shadow-[0_16px_32px_rgba(30,30,30,0.04)]"
                    >
                      <span
                        className={`grid h-10 w-10 sm:h-12 sm:w-12 shrink-0 place-items-center rounded-[0.75rem] sm:rounded-[1rem] transition-transform duration-500 ease-[cubic-bezier(0.16,1,0.3,1)] group-hover:scale-105 ${
                          item.tone === 'urgent' ? 'bg-[#FFF0EB] text-[#E54835]' : item.tone === 'soon' ? 'bg-[#FFF5E1] text-[#B45309]' : 'bg-[#E7ECFF] text-[#3D5CC7]'
                        }`}
                      >
                        {item.tone === 'info' ? <MessageCircle className="h-4 w-4 sm:h-5 sm:w-5" /> : <Clock3 className="h-4 w-4 sm:h-5 sm:w-5" />}
                      </span>
                      <div className="min-w-0 flex-1">
                        <p className="text-[9px] sm:text-[10px] font-black uppercase tracking-[0.15em] text-[#FF5A36] opacity-80 mb-0.5 sm:mb-1">{item.tag}</p>
                        <h3 className="truncate text-[14px] sm:text-[16px] font-black tracking-[-0.02em] text-[#171717]">{item.title}</h3>
                      </div>
                      <span className="shrink-0 rounded-full bg-black/5 px-2.5 py-1 sm:px-3 sm:py-1.5 text-[10px] sm:text-[11px] font-black text-[#74736D] transition-colors group-hover:bg-black/10">{item.time}</span>
                    </div>
                  ))}
                </div>

                <div className="mt-6 sm:mt-8 rounded-[1rem] sm:rounded-[1.5rem] border border-[#FAD7CD]/50 bg-gradient-to-br from-[#FFF0EB] to-[#FAD7CD] p-4 sm:p-5 shadow-[inset_0_1px_1px_rgba(255,255,255,0.8)]">
                  <div className="mb-2 sm:mb-3 flex items-center gap-2">
                    <Sparkles className="h-3.5 w-3.5 sm:h-4 sm:w-4 text-[#FF5A36]" />
                    <p className="text-[11px] sm:text-[12px] font-black uppercase tracking-[0.15em] text-[#D93A1C]">AI Insight</p>
                  </div>
                  <p className="text-[14px] sm:text-[16px] font-bold leading-relaxed text-[#3D332F]">
                    Your next deadline is close. Finish the report draft before registration closes on Friday.
                  </p>
                </div>
              </div>
            </div>

            {/* Floating Elements with Custom Physics */}
            <motion.div 
              animate={{ y: [0, -15, 0] }}
              transition={{ duration: 6, repeat: Infinity, ease: "easeInOut" }}
              className="absolute -left-6 sm:-left-12 lg:-left-24 top-16 -z-10 hidden w-32 sm:w-40 rotate-[-4deg] rounded-[1.5rem] sm:rounded-[2rem] border border-white/40 bg-[#D9F1EC]/90 p-4 sm:p-6 shadow-[0_24px_48px_rgba(30,30,30,0.08),inset_0_1px_1px_rgba(255,255,255,0.8)] backdrop-blur-xl md:block"
            >
              <Bell className="mb-2 sm:mb-4 h-6 w-6 sm:h-8 sm:w-8 text-[#1C8D5A]" />
              <p className="text-3xl sm:text-4xl font-black tracking-[-0.06em] text-[#0A472B]">3</p>
              <p className="mt-1 text-[9px] sm:text-[10px] font-black text-[#1C8D5A]/80 uppercase tracking-[0.2em]">urgent</p>
            </motion.div>

            <motion.div 
              animate={{ y: [0, 15, 0] }}
              transition={{ duration: 7, repeat: Infinity, ease: "easeInOut", delay: 1 }}
              className="absolute -bottom-8 right-0 hidden w-40 sm:w-52 rotate-[3deg] rounded-[1.5rem] sm:rounded-[2rem] border border-white/10 bg-[#171717] p-4 sm:p-6 text-white shadow-[0_32px_64px_rgba(30,30,30,0.3),inset_0_1px_1px_rgba(255,255,255,0.15)] backdrop-blur-xl sm:block sm:right-[-32px]"
            >
              <CheckCircle2 className="mb-2 sm:mb-4 h-6 w-6 sm:h-8 sm:w-8 text-[#D9F1EC]" />
              <p className="text-[14px] sm:text-[16px] font-black leading-snug tracking-[-0.01em]">Calendar updated automatically</p>
            </motion.div>
          </motion.div>
        </section>

        {/* 2B. Trusted by / Logo Wall — UNDER the hero, never inside it */}
        <section className="pb-8 sm:pb-16">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
            className="flex flex-col items-center gap-8"
          >
            <p className="text-[10px] sm:text-[11px] font-black uppercase tracking-[0.22em] text-[#A3A29C]">Used by students at</p>
            <div className="flex flex-wrap items-center justify-center gap-x-12 gap-y-4 opacity-50">
              {/* 
                LOGO PLACEHOLDER — University / institution logos
                Replace with actual SVG logos from Simple Icons or brand assets.
                Suggested: {"University of Lagos", "Obafemi Awolowo University", "University of Ibadan", "Covenant University", "UNILAG"}
                Format: SVG monochrome (#74736D), ~120px wide each.
              */}
              <div className="flex items-center gap-2 text-[15px] font-black tracking-[-0.02em] text-[#74736D]">
                <div className="w-6 h-6 rounded-md bg-[#74736D]/10 flex items-center justify-center text-[8px] font-bold">U</div>
                UniLag
              </div>
              <div className="flex items-center gap-2 text-[15px] font-black tracking-[-0.02em] text-[#74736D]">
                <div className="w-6 h-6 rounded-md bg-[#74736D]/10 flex items-center justify-center text-[8px] font-bold">O</div>
                OAU
              </div>
              <div className="flex items-center gap-2 text-[15px] font-black tracking-[-0.02em] text-[#74736D]">
                <div className="w-6 h-6 rounded-md bg-[#74736D]/10 flex items-center justify-center text-[8px] font-bold">U</div>
                UniIbadan
              </div>
              <div className="flex items-center gap-2 text-[15px] font-black tracking-[-0.02em] text-[#74736D]">
                <div className="w-6 h-6 rounded-md bg-[#74736D]/10 flex items-center justify-center text-[8px] font-bold">C</div>
                Covenant U
              </div>
            </div>
          </motion.div>
        </section>

        {/* 2D. Stats band — quantified credibility */}
        <section className="py-8 sm:py-12">
          <motion.div
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true, margin: "-80px" }}
            variants={staggerContainer}
            className="grid grid-cols-2 lg:grid-cols-4 gap-px overflow-hidden rounded-[2rem] sm:rounded-[2.5rem] border border-black/[0.04] bg-black/[0.04]"
          >
            {[
              { stat: '12k+', label: 'Deadlines caught', sub: 'auto-extracted this term' },
              { stat: '3.4 hrs', label: 'Saved per week', sub: 'no more scrolling chats' },
              { stat: '98.6%', label: 'Extraction accuracy', sub: 'across academic contexts' },
              { stat: '<2 min', label: 'Daily briefing', sub: 'from noise to clarity' },
            ].map((s) => (
              <motion.div
                key={s.label}
                variants={fadeUp}
                className="bg-[#FDFDFD] p-6 sm:p-8 lg:p-10 flex flex-col gap-1.5 sm:gap-2 transition-colors duration-500 hover:bg-white"
              >
                <p className="text-[clamp(28px,4vw,44px)] font-black leading-none tracking-[-0.05em] text-[#171717]">
                  {s.stat}
                </p>
                <p className="text-[13px] sm:text-[15px] font-black tracking-[-0.01em] text-[#171717]">{s.label}</p>
                <p className="text-[11px] sm:text-[12px] font-medium text-[#A3A29C]">{s.sub}</p>
              </motion.div>
            ))}
          </motion.div>
        </section>

        {/* 2C. App Mockup — Phone-frame product showcase */}
        <section className="py-20 sm:py-28 lg:py-36 relative overflow-hidden" id="product">
          {/* Ambient mesh background */}
          <div className="pointer-events-none absolute inset-0 -z-10">
            <div className="absolute -top-32 left-1/2 -translate-x-1/2 h-[420px] w-[820px] rounded-full bg-[radial-gradient(closest-side,rgba(255,90,54,0.18),transparent_70%)] blur-3xl" />
            <div className="absolute bottom-0 right-0 h-[320px] w-[520px] rounded-full bg-[radial-gradient(closest-side,rgba(124,107,224,0.12),transparent_70%)] blur-3xl" />
          </div>

          {/* Section header */}
          <motion.div
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true, margin: "-80px" }}
            variants={fadeUp}
            className="flex flex-col items-center text-center max-w-[760px] mx-auto mb-12 sm:mb-16 px-4"
          >
            <span className="mb-4 inline-flex items-center gap-2 rounded-full border border-black/5 bg-white/70 px-3.5 py-1.5 text-[10px] sm:text-[11px] font-black uppercase tracking-[0.22em] text-[#C83C21] shadow-[0_2px_8px_rgba(0,0,0,0.02)] backdrop-blur-md">
              <span className="h-1.5 w-1.5 rounded-full bg-[#FF5A36] animate-pulse" />
              Live product
            </span>
            <h2 className="text-[clamp(32px,5vw,56px)] font-black leading-[0.95] tracking-[-0.05em]">
              From chat noise to <span className="text-transparent bg-clip-text bg-gradient-to-br from-[#FF5A36] to-[#D93A1C]">calendar clarity</span>.
            </h2>
            <p className="mt-4 sm:mt-5 text-[16px] sm:text-[19px] font-medium leading-relaxed text-[#5F5F59] max-w-[560px]">
              One WhatsApp message in. One deadline on your calendar out. No screenshots, no scrolling back.
            </p>
          </motion.div>

          {/* Mockup stage */}
          <div className="relative mx-auto max-w-[1180px] px-4 sm:px-6">
            {/* Ground shadow plate */}
            <div className="absolute inset-x-0 top-1/2 -z-10 mx-auto h-[120px] w-[80%] max-w-[700px] -translate-y-1/2 rounded-full bg-[#FF5A36]/15 blur-3xl" />

            <div className="relative grid items-center gap-10 lg:grid-cols-[1fr_auto_1fr] lg:gap-6">

              {/* ── LEFT: WhatsApp screenshot slot ── */}
              <motion.div
                initial={{ opacity: 0, x: -40, rotate: -8, filter: 'blur(8px)' }}
                whileInView={{ opacity: 1, x: 0, rotate: -3, filter: 'blur(0px)' }}
                viewport={{ once: true, margin: "-60px" }}
                transition={{ duration: 1.2, ease: [0.16, 1, 0.3, 1] }}
                className="hidden lg:block justify-self-end"
              >
                {/* IMAGE PLACEHOLDER — WhatsApp thread with Knowtis reading message
                    Drop in: public/mockups/whatsapp-thread.png
                    Recommended: PNG/WebP, transparent or warm bg, ~600x880 (3:4.4 portrait).
                    Aspect: 290x420 reserved so layout stays stable until image loads. */}
                <div className="relative w-[290px] h-[420px] rounded-[1.75rem] border-2 border-dashed border-black/10 bg-[#F4F3EF] shadow-[0_30px_70px_rgba(30,30,30,0.18)] overflow-hidden">
                  {/* Fallback shown by default; hidden once the <img> below loads. */}
                  <div data-fallback className="absolute inset-0 flex flex-col items-center justify-center gap-2 p-6 text-center">
                    <ImageIcon className="h-7 w-7 text-[#A3A29C]" strokeWidth={1.5} />
                    <p className="text-[11px] font-black uppercase tracking-[0.2em] text-[#74736D]">WhatsApp slot</p>
                    <p className="text-[10.5px] font-semibold text-[#A3A29C]">public/mockups/whatsapp-thread.png</p>
                    <p className="text-[10px] font-medium text-[#C9C9C4]">~600×880 · 3:4.4</p>
                  </div>
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src="/mockups/whatsapp-thread.png"
                    alt="WhatsApp class group chat being processed by Knowtis"
                    width={290}
                    height={420}
                    loading="lazy"
                    onLoad={(e) => {
                      (e.currentTarget as HTMLImageElement).style.display = 'block';
                      const fb = (e.currentTarget.previousElementSibling as HTMLElement | null);
                      if (fb) fb.style.display = 'none';
                    }}
                    onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = 'none'; }}
                    className="absolute inset-0 hidden w-full h-full object-cover"
                  />
                </div>
              </motion.div>

              {/* ── CENTER: Phone / dashboard screenshot slot ── */}
              <motion.div
                initial={{ opacity: 0, y: 60, filter: 'blur(12px)' }}
                whileInView={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
                viewport={{ once: true, margin: "-60px" }}
                transition={{ duration: 1.4, ease: [0.16, 1, 0.3, 1] }}
                className="relative mx-auto"
                style={{ width: 'min(340px, 100%)' }}
              >
                {/* IMAGE PLACEHOLDER — main app mockup (dashboard / "Today" view)
                    Drop in: public/mockups/app-dashboard.png
                    Recommended: PNG with transparent background. Crop should already
                    include phone frame + notch if desired, or just the screen content.
                    Aspect: 340x740 (matches iPhone 15 Pro Max logical ratio). */}
                <div className="relative w-full h-[740px] rounded-[3rem] border-2 border-dashed border-black/10 bg-gradient-to-b from-[#F4F3EF] to-[#E9E9E6] shadow-[0_60px_120px_rgba(20,20,20,0.45)] overflow-hidden">
                  <div data-fallback className="absolute inset-0 flex flex-col items-center justify-center gap-3 p-8 text-center">
                    <div className="grid h-16 w-16 place-items-center rounded-[1.25rem] bg-white shadow-[0_8px_24px_rgba(0,0,0,0.06)]">
                      <ImageIcon className="h-7 w-7 text-[#FF5A36]" strokeWidth={1.5} />
                    </div>
                    <p className="text-[11px] font-black uppercase tracking-[0.22em] text-[#74736D]">App mockup slot</p>
                    <p className="text-[11px] font-semibold text-[#A3A29C]">public/mockups/app-dashboard.png</p>
                    <p className="text-[10px] font-medium text-[#C9C9C4]">~680×1480 · phone portrait</p>
                  </div>
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src="/mockups/app-dashboard.png"
                    alt="Knowtis dashboard showing today's deadlines and AI catch-up"
                    width={340}
                    height={740}
                    loading="lazy"
                    onLoad={(e) => {
                      (e.currentTarget as HTMLImageElement).style.display = 'block';
                      const fb = (e.currentTarget.previousElementSibling as HTMLElement | null);
                      if (fb) fb.style.display = 'none';
                    }}
                    onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = 'none'; }}
                    className="absolute inset-0 hidden w-full h-full object-contain p-3"
                  />
                </div>

                {/* Subtle floating disk behind phone for depth */}
                <div className="pointer-events-none absolute inset-0 -z-10 m-auto h-[420px] w-[420px] rounded-full bg-[radial-gradient(closest-side,rgba(255,90,54,0.1),transparent_70%)]" />
              </motion.div>

              {/* ── RIGHT: Calendar / extracted event slot ── */}
              <motion.div
                initial={{ opacity: 0, x: 40, rotate: 8, filter: 'blur(8px)' }}
                whileInView={{ opacity: 1, x: 0, rotate: 3, filter: 'blur(0px)' }}
                viewport={{ once: true, margin: "-60px" }}
                transition={{ duration: 1.2, ease: [0.16, 1, 0.3, 1] }}
                className="hidden lg:block justify-self-start"
              >
                {/* IMAGE PLACEHOLDER — calendar / extracted event visual
                    Drop in: public/mockups/calendar-event.png
                    Recommended: PNG/WebP, transparent or white bg, ~600x880 (3:4.4 portrait). */}
                <div className="relative w-[290px] h-[420px] rounded-[1.75rem] border-2 border-dashed border-black/10 bg-white shadow-[0_30px_70px_rgba(30,30,30,0.16)] overflow-hidden">
                  <div data-fallback className="absolute inset-0 flex flex-col items-center justify-center gap-2 p-6 text-center">
                    <ImageIcon className="h-7 w-7 text-[#A3A29C]" strokeWidth={1.5} />
                    <p className="text-[11px] font-black uppercase tracking-[0.2em] text-[#74736D]">Calendar slot</p>
                    <p className="text-[10.5px] font-semibold text-[#A3A29C]">public/mockups/calendar-event.png</p>
                    <p className="text-[10px] font-medium text-[#C9C9C4]">~600×880 · 3:4.4</p>
                  </div>
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src="/mockups/calendar-event.png"
                    alt="Calendar week view with auto-added deadline highlighted"
                    width={290}
                    height={420}
                    loading="lazy"
                    onLoad={(e) => {
                      (e.currentTarget as HTMLImageElement).style.display = 'block';
                      const fb = (e.currentTarget.previousElementSibling as HTMLElement | null);
                      if (fb) fb.style.display = 'none';
                    }}
                    onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = 'none'; }}
                    className="absolute inset-0 hidden w-full h-full object-cover"
                  />
                </div>
              </motion.div>
            </div>

            {/* Caption row under the showcase (feature pills) */}
            <motion.div
              initial="hidden"
              whileInView="visible"
              viewport={{ once: true, margin: "-40px" }}
              variants={staggerContainer}
              className="mx-auto mt-12 sm:mt-16 flex flex-wrap items-center justify-center gap-3 sm:gap-4 max-w-[820px]"
            >
              {[
                { icon: Zap, label: 'Real-time extraction', color: '#FF5A36', bg: '#FFF0EB' },
                { icon: CalendarDays, label: 'Auto calendar entry', color: '#1C8D5A', bg: '#D9F1EC' },
                { icon: Bell, label: 'Priority pings only', color: '#7C6BE0', bg: '#E7ECFF' },
                { icon: Sparkles, label: 'Groq-powered briefs', color: '#B45309', bg: '#FFF5E1' },
              ].map(({ icon: Icon, label, color, bg }) => (
                <motion.div
                  key={label}
                  variants={fadeUp}
                  className="flex items-center gap-2 rounded-full bg-white/80 px-4 py-2 shadow-[0_8px_24px_rgba(30,30,30,0.04),inset_0_1px_0_rgba(255,255,255,1)] ring-1 ring-black/5 backdrop-blur-sm"
                >
                  <span className="grid h-6 w-6 place-items-center rounded-full" style={{ backgroundColor: bg, color }}>
                    <Icon className="h-3.5 w-3.5" strokeWidth={2.2} />
                  </span>
                  <span className="text-[12px] font-black tracking-[-0.01em] text-[#171717]">{label}</span>
                </motion.div>
              ))}
            </motion.div>
          </div>
        </section>

        {/* 3. How It Works — 3-step process */}
        <section className="py-16 lg:py-24">
          <motion.div
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true, margin: "-100px" }}
            variants={fadeUp}
            className="flex flex-col items-center text-center max-w-[800px] mx-auto mb-14 sm:mb-18"
          >
            <span className="mb-4 rounded-full bg-black/5 px-4 py-1.5 text-[10px] sm:text-[11px] font-black uppercase tracking-[0.2em] text-[#74736D]">How it works</span>
            <h2 className="text-[clamp(32px,5vw,52px)] font-black leading-[0.96] tracking-[-0.05em]">Three steps to clarity.</h2>
            <p className="mt-4 text-[17px] font-medium leading-relaxed text-[#5F5F59] max-w-[500px]">From chaotic group chat to organised academic timeline — in minutes.</p>
          </motion.div>

          <div className="grid md:grid-cols-3 gap-8 max-w-[1000px] mx-auto">
            {[
              { step: '01', title: 'Connect a group', desc: 'Paste your WhatsApp invite link. Knowtis joins silently as a watcher — no DMs, no outbound messages.', color: 'from-[#FFF0EB] to-[#FFE6DE]', icon: '🔗' },
              { step: '02', title: 'AI listens & extracts', desc: 'Messages are classified, deduplicated, and converted into structured academic events with urgency scores.', color: 'from-[#FFF5E1] to-[#FFE8AF]', icon: '⚡' },
              { step: '03', title: 'Your briefing is ready', desc: 'Deadlines, alerts, and schedule changes appear in your dashboard, widgets, and daily Night Brief.', color: 'from-[#E7ECFF] to-[#D4C5F9]', icon: '📋' },
            ].map((step, i) => (
              <motion.div
                key={step.step}
                initial={{ opacity: 0, y: 40, filter: 'blur(8px)' }}
                whileInView={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.15, duration: 1, ease: [0.16, 1, 0.3, 1] }}
                className="relative flex flex-col items-center text-center"
              >
                {/* Step number badge */}
                <div className={`w-16 h-16 rounded-full bg-gradient-to-br ${step.color} flex items-center justify-center text-xl font-black text-[#171717] shadow-sm mb-5`}>
                  {step.step}
                </div>
                {/* Connector line (hidden on mobile) */}
                {i < 2 && (
                  <div className="hidden md:block absolute top-8 left-[calc(50%+3rem)] w-[calc(100%-6rem)] h-px bg-gradient-to-r from-[#FF5A36]/20 to-transparent" />
                )}
                <h3 className="text-xl sm:text-2xl font-black tracking-[-0.02em] mb-3">{step.title}</h3>
                <p className="text-[15px] font-medium text-[#74736D] leading-relaxed max-w-[260px]">{step.desc}</p>
              </motion.div>
            ))}
          </div>
        </section>

        {/* 3. What you get (Benefits Section) - py-24 lg:py-40 spacing */}
        <section className="py-24 lg:py-40" id="benefits">
          <motion.div 
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true, margin: "-100px" }}
            variants={fadeUp}
            className="flex flex-col items-center text-center max-w-[800px] mx-auto mb-16 sm:mb-20"
          >
            <span className="mb-4 sm:mb-6 rounded-full bg-black/5 px-4 py-1.5 text-[10px] sm:text-[11px] font-black uppercase tracking-[0.2em] text-[#74736D]">What you get</span>
            <h2 className="text-[clamp(36px,6vw,64px)] font-black leading-[0.96] tracking-[-0.05em]">Filter the noise.</h2>
            <p className="mt-4 sm:mt-6 text-[17px] sm:text-[20px] font-medium leading-relaxed text-[#5F5F59]">The product keeps the familiar group-chat flow, then removes the mental sorting work entirely.</p>
          </motion.div>

          <motion.div 
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true, margin: "-100px" }}
            variants={staggerContainer}
            className="grid gap-6 md:grid-cols-3"
          >
            {benefits.map((benefit, bIdx) => (
              <motion.article
                variants={fadeUpScale}
                key={benefit.title}
                className="group rounded-[2rem] sm:rounded-[2.5rem] bg-black/[0.02] p-1.5 sm:p-2 border border-black/[0.04] transition-all duration-500 ease-[cubic-bezier(0.16,1,0.3,1)] hover:bg-black/[0.04]"
              >
                <div className="h-full w-full rounded-[calc(2rem-0.5rem)] sm:rounded-[calc(2.5rem-0.5rem)] bg-white p-6 sm:p-10 shadow-[0_24px_54px_rgba(0,0,0,0.02),inset_0_1px_0_rgba(255,255,255,1)] flex flex-col items-center text-center transition-transform duration-500 ease-[cubic-bezier(0.16,1,0.3,1)] group-hover:scale-[0.99]">
                  <div className="mb-6 sm:mb-8 grid h-14 w-14 sm:h-16 sm:w-16 place-items-center rounded-[1rem] sm:rounded-[1.25rem] shadow-[inset_0_1px_1px_rgba(255,255,255,0.8)] bg-gradient-to-b from-[#FFF0EB] to-[#FFE6DE] text-[#FF5A36] transition-transform duration-500 ease-[cubic-bezier(0.16,1,0.3,1)] group-hover:scale-110 group-hover:-translate-y-1">
                    <benefit.icon className="h-6 w-6 sm:h-7 sm:w-7" strokeWidth={2} />
                  </div>
                  <h3 className="text-[22px] sm:text-[26px] font-black tracking-[-0.04em]">{benefit.title}</h3>
                  <p className="mt-3 sm:mt-4 text-[15px] sm:text-[16px] font-medium leading-relaxed text-[#74736D]">{benefit.copy}</p>

                  {/* ── Benefit card visual (varies per card index) ── */}
                  {bIdx === 0 && (
                    <>
                      {/* 
                        IMAGE PLACEHOLDER — "Scans group noise" visual
                        Recommended image: Split-screen showing chaotic WhatsApp group chat (left) → clean structured Knowtis timeline (right). 
                        Format: 16:9, PNG/webp, ~800×600px. Orange accent (#FF5A36) against warm off-white.
                      */}
                      <div className="mt-8 sm:mt-12 h-32 sm:h-36 w-full rounded-[1.25rem] sm:rounded-[1.5rem] border border-black/5 bg-gradient-to-br from-[#FFF0EB] to-[#FFE6DE] flex items-center justify-center overflow-hidden relative group">
                        <div className="absolute inset-0 opacity-[0.07] pointer-events-none" style={{
                          backgroundImage: `url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23FF5A36' fill-opacity='1'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E")`,
                          backgroundSize: '30px 30px'
                        }} />
                        <div className="relative z-10 flex flex-col items-center gap-2">
                          <div className="flex -space-x-3">
                            <div className="w-8 h-8 rounded-full bg-white/80 border border-white shadow-sm flex items-center justify-center text-[10px] font-bold text-[#5F5F59]">💬</div>
                            <div className="w-8 h-8 rounded-full bg-white/80 border border-white shadow-sm flex items-center justify-center text-[10px] font-bold text-[#1C8D5A]">✓</div>
                            <div className="w-8 h-8 rounded-full bg-[#FF5A36] shadow-[0_4px_12px_rgba(255,90,54,0.3)] flex items-center justify-center text-[10px] font-bold text-white">K</div>
                          </div>
                          <p className="text-[9px] font-black uppercase tracking-[0.18em] text-[#C83C21]">WhatsApp Noise → Structured Events</p>
                        </div>
                      </div>
                    </>
                  )}
                  {bIdx === 1 && (
                    <>
                      {/* 
                        IMAGE PLACEHOLDER — "Builds your calendar" visual
                        Recommended image: Monthly/weekly calendar view with deadlines auto-populated (orange pins/dots). 
                        Format: 16:9, PNG/webp, ~800×600px. Warm amber palette.
                      */}
                      <div className="mt-8 sm:mt-12 h-32 sm:h-36 w-full rounded-[1.25rem] sm:rounded-[1.5rem] border border-black/5 bg-gradient-to-br from-[#FFF5E1] to-[#FFE8AF] flex items-center justify-center overflow-hidden relative group">
                        <div className="absolute inset-0 opacity-[0.06] pointer-events-none" style={{
                          backgroundImage: `url("data:image/svg+xml,%3Csvg width='40' height='40' viewBox='0 0 40 40' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='%23F2A53C' fill-opacity='1' fill-rule='evenodd'%3E%3Cpath d='M0 40L40 0H20L0 20M40 40V20L20 40'/%3E%3C/g%3E%3C/svg%3E")`,
                          backgroundSize: '24px 24px'
                        }} />
                        <div className="relative z-10 flex flex-col items-center gap-2">
                          <div className="flex items-center gap-2">
                            <div className="w-6 h-6 rounded-md bg-white/90 border border-white shadow-sm flex items-center justify-center text-[8px] font-bold text-[#B45309]">15</div>
                            <div className="w-6 h-6 rounded-md bg-[#FF5A36] shadow-sm flex items-center justify-center text-[8px] font-bold text-white">16</div>
                            <div className="w-6 h-6 rounded-md bg-white/90 border border-white shadow-sm flex items-center justify-center text-[8px] font-bold text-[#B45309]">17</div>
                          </div>
                          <p className="text-[9px] font-black uppercase tracking-[0.18em] text-[#B45309]">Calendar auto-sync</p>
                        </div>
                      </div>
                    </>
                  )}
                  {bIdx === 2 && (
                    <>
                      {/* 
                        IMAGE PLACEHOLDER — "Explains what matters" visual
                        Recommended image: AI chat interface showing a student asking "What's due tomorrow?" with structured response listing deadlines.
                        Format: 16:9, PNG/webp, ~800×600px. Lavender/purple-tinged palette (#D4C5F9) with orange accent.
                      */}
                      <div className="mt-8 sm:mt-12 h-32 sm:h-36 w-full rounded-[1.25rem] sm:rounded-[1.5rem] border border-black/5 bg-gradient-to-br from-[#E7ECFF] to-[#D4C5F9] flex items-center justify-center overflow-hidden relative group">
                        <div className="absolute inset-0 opacity-[0.07] pointer-events-none" style={{
                          backgroundImage: `url("data:image/svg+xml,%3Csvg width='32' height='32' viewBox='0 0 32 32' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='%234F46E5' fill-opacity='0.08' fill-rule='evenodd'%3E%3Ccircle cx='16' cy='16' r='2'/%3E%3C/g%3E%3C/svg%3E")`,
                          backgroundSize: '20px 20px'
                        }} />
                        <div className="relative z-10 flex flex-col items-center gap-2">
                          <div className="flex items-start gap-2 max-w-[180px]">
                            <div className="w-6 h-5 rounded-md bg-white/90 border border-white shadow-sm flex items-center justify-center text-[7px] font-bold text-[#4F46E5] shrink-0 mt-0.5">?</div>
                            <p className="text-[8px] font-bold text-[#3D2E7C] text-left leading-tight">"What's due tomorrow?"</p>
                          </div>
                          <div className="w-[140px] h-[2px] rounded-full bg-white/60" />
                          <p className="text-[8px] font-bold text-[#4F46E5]">→ ELE310 Quiz, CSC301 Assignment</p>
                          <p className="text-[9px] font-black uppercase tracking-[0.18em] text-[#4F46E5]">AI Catch-Up Agent</p>
                        </div>
                      </div>
                    </>
                  )}
                </div>
              </motion.article>
            ))}
          </motion.div>
        </section>

        {/* 4. For who? (Apply Cases) */}
        <section className="py-24 lg:py-40 relative" id="how">
          {/* Subtle background container instead of full bleed block */}
          <div className="absolute inset-0 bg-[#F4F3EF]/50 rounded-[3rem] sm:rounded-[4rem] -mx-4 sm:-mx-8 lg:-mx-12 -z-10" />
          
          <motion.div 
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true, margin: "-100px" }}
            variants={fadeUp}
            className="flex flex-col items-center text-center max-w-[800px] mx-auto mb-16 sm:mb-20"
          >
            <span className="mb-4 sm:mb-6 rounded-full bg-white px-4 py-1.5 text-[10px] sm:text-[11px] font-black uppercase tracking-[0.2em] text-[#74736D] shadow-sm">Target Audience</span>
            <h2 className="text-[clamp(36px,6vw,64px)] font-black leading-[0.96] tracking-[-0.05em]">For who?</h2>
            <p className="mt-4 sm:mt-6 text-[17px] sm:text-[20px] font-medium leading-relaxed text-[#5F5F59]">Knowtis is built for students who want to stay informed without getting overwhelmed.</p>
          </motion.div>

          <div className="grid md:grid-cols-3 gap-6 relative max-w-[1000px] mx-auto">
            {applyCases.map((caseItem, i) => (
              <motion.div 
                key={caseItem.title}
                initial={{ opacity: 0, y: 40, filter: 'blur(8px)' }}
                whileInView={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
                transition={{ delay: i * 0.15, duration: 1.2, ease: [0.16, 1, 0.3, 1] }}
                viewport={{ once: true }}
                className="relative z-10 flex flex-col items-center text-center bg-white p-8 sm:p-10 rounded-[2rem] sm:rounded-[2.5rem] shadow-[0_12px_32px_rgba(0,0,0,0.02),inset_0_1px_0_rgba(255,255,255,1)] border border-black/[0.04]"
              >
                <div className="h-20 w-20 sm:h-24 sm:w-24 rounded-full bg-[#FFF0EB] border border-[#FFD8CD]/50 flex items-center justify-center text-[#FF5A36] mb-6 sm:mb-8 shadow-[inset_0_1px_1px_rgba(255,255,255,0.8)]">
                  <caseItem.icon className="h-8 w-8 sm:h-10 sm:w-10" strokeWidth={1.5} />
                </div>
                <h3 className="text-xl sm:text-2xl font-black tracking-[-0.02em] mb-3 sm:mb-4">{caseItem.title}</h3>
                <p className="text-[15px] sm:text-[16px] font-medium text-[#74736D] leading-relaxed">{caseItem.copy}</p>
              </motion.div>
            ))}
          </div>
        </section>

        {/* 5. Features you'll love (Asymmetrical Bento) */}
        <section className="py-24 lg:py-40" id="features">
          <motion.div 
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true, margin: "-100px" }}
            variants={fadeUp}
            className="flex flex-col items-center text-center max-w-[800px] mx-auto mb-16 sm:mb-20"
          >
            <span className="mb-4 sm:mb-6 rounded-full bg-black/5 px-4 py-1.5 text-[10px] sm:text-[11px] font-black uppercase tracking-[0.2em] text-[#74736D]">Features</span>
            <h2 className="text-[clamp(36px,6vw,64px)] font-black leading-[0.96] tracking-[-0.05em]">Everything you need.</h2>
          </motion.div>

          <div className="grid grid-cols-1 md:grid-cols-12 gap-5 sm:gap-6 auto-rows-auto md:auto-rows-[240px]">
            {/* Feature 0 (Large) */}
            <motion.div
              initial="hidden" whileInView="visible" viewport={{ once: true, margin: "-100px" }} variants={fadeUpScale}
              className="md:col-span-8 md:row-span-2 group rounded-[2rem] sm:rounded-[2.5rem] bg-black/[0.02] p-1.5 sm:p-2 border border-black/[0.04]"
            >
              <div className="h-full w-full rounded-[calc(2rem-0.5rem)] sm:rounded-[calc(2.5rem-0.5rem)] bg-white p-6 sm:p-12 shadow-sm flex flex-col">
                <div className="h-10 w-10 sm:h-12 sm:w-12 rounded-[0.75rem] sm:rounded-[1rem] bg-[#F4F3EF] text-[#74736D] flex items-center justify-center mb-5 sm:mb-6 group-hover:bg-[#FF5A36] group-hover:text-white transition-colors duration-500">
                  {(() => {
                    const Icon0 = features[0].icon;
                    return <Icon0 className="h-5 w-5 sm:h-6 sm:w-6" />;
                  })()}
                </div>
                <h4 className="text-2xl sm:text-3xl font-black tracking-tight mb-3 sm:mb-4">{features[0].title}</h4>
                <p className="text-[15px] sm:text-[17px] font-medium text-[#74736D] leading-relaxed max-w-[400px] mb-6 sm:mb-0">{features[0].desc}</p>
                {/* 
                    IMAGE PLACEHOLDER — AI Chat Summaries visual
                    Recommended image: A phone or web UI mockup showing a conversation-style AI summary: "While you were away: 1 deadline added, 1 class cancelled, 2 new notices."
                    Format: 16:9 landscape, PNG/webp, ~1200×600px. Orange (#FF5A36) accent bubbles on white background, clean sans-serif.
                  */}
                  <div className="mt-auto h-40 sm:h-48 w-full rounded-[1.25rem] sm:rounded-[1.5rem] border border-black/5 bg-gradient-to-br from-[#F4F3EF] to-white flex items-center justify-center overflow-hidden relative">
                    <div className="absolute inset-0 opacity-[0.05] pointer-events-none" style={{
                      backgroundImage: `url("data:image/svg+xml,%3Csvg width='40' height='40' viewBox='0 0 40 40' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='%23FF5A36' fill-opacity='1'%3E%3Ccircle cx='20' cy='20' r='1.5'/%3E%3C/g%3E%3C/svg%3E")`,
                      backgroundSize: '24px 24px'
                    }} />
                    <div className="relative z-10 flex flex-col items-start gap-2 w-full px-6">
                      <div className="flex items-center gap-2">
                        <Sparkles className="h-3 w-3 text-[#FF5A36]" />
                        <span className="text-[7px] font-black uppercase tracking-[0.2em] text-[#C83C21]">AI Summary</span>
                      </div>
                      <div className="space-y-1.5 w-full">
                        <div className="h-2.5 w-[85%] rounded-full bg-[#FFE6DE] animate-pulse" />
                        <div className="h-2.5 w-[65%] rounded-full bg-[#F4F3EF]" />
                        <div className="h-2.5 w-[75%] rounded-full bg-[#FFF5E1]" />
                      </div>
                      <div className="flex items-center gap-1.5 mt-1">
                        <span className="inline-flex items-center rounded-full bg-[#FF5A36]/10 px-2 py-0.5 text-[6px] font-bold text-[#C83C21]">3 updates</span>
                        <span className="inline-flex items-center rounded-full bg-[#1C8D5A]/10 px-2 py-0.5 text-[6px] font-bold text-[#047857]">1 urgent</span>
                      </div>
                    </div>
                  </div>
              </div>
            </motion.div>

            {/* Feature 1 — Auto-Calendar Sync */}
            <motion.div
              initial="hidden" whileInView="visible" viewport={{ once: true, margin: "-100px" }} variants={fadeUpScale} transition={{ delay: 0.1 }}
              className="md:col-span-4 md:row-span-1 rounded-[2rem] sm:rounded-[2.5rem] bg-black/[0.02] p-1.5 sm:p-2 border border-black/[0.04]"
            >
              <div className="h-full w-full rounded-[calc(2rem-0.5rem)] sm:rounded-[calc(2.5rem-0.5rem)] bg-white p-6 sm:p-8 shadow-sm flex flex-col group hover:shadow-md transition-shadow duration-500">
                <div className="h-10 w-10 rounded-full bg-[#F4F3EF] text-[#74736D] flex items-center justify-center mb-4 group-hover:bg-[#FF5A36] group-hover:text-white transition-colors duration-500">
                  {(() => {
                    const Icon1 = features[1].icon;
                    return <Icon1 className="h-5 w-5" />;
                  })()}
                </div>
                <h4 className="text-lg sm:text-xl font-black tracking-tight mb-2">{features[1].title}</h4>
                <p className="text-[14px] sm:text-[15px] font-medium text-[#74736D] leading-relaxed mb-4">{features[1].desc}</p>
                {/* 
                  IMAGE PLACEHOLDER — Calendar Sync visual
                  Format: small calendar icon + sync arrow, warm amber tones.
                */}
                <div className="mt-auto h-8 w-full rounded-lg bg-gradient-to-r from-[#FFF5E1] to-[#FFE8AF] flex items-center justify-center">
                  <div className="flex gap-1 items-center">
                    <div className="w-3 h-3 rounded-[2px] bg-white border border-[#B45309]/20 flex items-center justify-center text-[4px] font-bold text-[#B45309]">16</div>
                    <CalendarDays className="h-3 w-3 text-[#B45309]" />
                    <span className="text-[6px] font-bold text-[#B45309] uppercase tracking-[0.1em]">synced</span>
                  </div>
                </div>
              </div>
            </motion.div>

            {/* Feature 2 — Priority Alerts */}
            <motion.div
              initial="hidden" whileInView="visible" viewport={{ once: true, margin: "-100px" }} variants={fadeUpScale} transition={{ delay: 0.2 }}
              className="md:col-span-4 md:row-span-1 rounded-[2rem] sm:rounded-[2.5rem] bg-black/[0.02] p-1.5 sm:p-2 border border-black/[0.04]"
            >
              <div className="h-full w-full rounded-[calc(2rem-0.5rem)] sm:rounded-[calc(2.5rem-0.5rem)] bg-white p-6 sm:p-8 shadow-sm flex flex-col group hover:shadow-md transition-shadow duration-500">
                <div className="h-10 w-10 rounded-full bg-[#F4F3EF] text-[#74736D] flex items-center justify-center mb-4 group-hover:bg-[#FF5A36] group-hover:text-white transition-colors duration-500">
                  {(() => {
                    const Icon2 = features[2].icon;
                    return <Icon2 className="h-5 w-5" />;
                  })()}
                </div>
                <h4 className="text-lg sm:text-xl font-black tracking-tight mb-2">{features[2].title}</h4>
                <p className="text-[14px] sm:text-[15px] font-medium text-[#74736D] leading-relaxed mb-4">{features[2].desc}</p>
                {/* 
                  IMAGE PLACEHOLDER — Priority Alerts visual
                  Format: small notification bell with priority badge, coral-toned.
                */}
                <div className="mt-auto h-8 w-full rounded-lg bg-gradient-to-r from-[#FFF0EB] to-[#FFE6DE] flex items-center justify-center">
                  <div className="flex gap-1.5 items-center">
                    <span className="inline-flex items-center gap-1 rounded-full bg-white/80 px-2 py-0.5 text-[6px] font-bold text-[#C83C21]">
                      <Bell className="h-2.5 w-2.5" />
                      ALERT
                    </span>
                    <span className="text-[6px] font-bold text-[#C83C21]">ELE310 Quiz moved → Fri</span>
                  </div>
                </div>
              </div>
            </motion.div>

            {/* Feature 3, 4, 5 (Bottom Row) */}
            {[3, 4, 5].map((idx, i) => {
              const IconComp = features[idx].icon;
              const visualLabels = ['Smart Silencing', 'Deadline Tracking', 'Deep Search'];
              const visualColors = [
                'from-[#F4F3EF] to-[#E9E9E6]',
                'from-[#FFF5E1] to-[#FFE8AF]',
                'from-[#E7ECFF] to-[#D4C5F9]'
              ];
              const visualTexts = [
                'mute casual chat & memes',
                'countdown to submission',
                'search past announcements'
              ];
              return (
              <motion.div
                key={idx}
                initial="hidden" whileInView="visible" viewport={{ once: true, margin: "-100px" }} variants={fadeUpScale} transition={{ delay: i * 0.1 }}
                className="md:col-span-4 md:row-span-1 rounded-[2rem] sm:rounded-[2.5rem] bg-black/[0.02] p-1.5 sm:p-2 border border-black/[0.04]"
              >
                <div className="h-full w-full rounded-[calc(2rem-0.5rem)] sm:rounded-[calc(2.5rem-0.5rem)] bg-white p-6 sm:p-8 shadow-sm flex flex-col group hover:shadow-md transition-shadow duration-500">
                  <div className="h-10 w-10 rounded-full bg-[#F4F3EF] text-[#74736D] flex items-center justify-center mb-4 group-hover:bg-[#FF5A36] group-hover:text-white transition-colors duration-500">
                    <IconComp className="h-5 w-5" />
                  </div>
                  <h4 className="text-lg sm:text-xl font-black tracking-tight mb-2">{features[idx].title}</h4>
                  <p className="text-[14px] sm:text-[15px] font-medium text-[#74736D] leading-relaxed">{features[idx].desc}</p>
                  {/* 
                    IMAGE PLACEHOLDER — {features[idx].title} visual
                    Format: 16:9, ~400×200px. Minimal icon + label on tinted gradient.
                  */}
                  <div className={`mt-3 h-7 w-full rounded-lg bg-gradient-to-r ${visualColors[i]} flex items-center justify-center`}>
                    <span className="text-[6px] font-bold text-[#5F5F59] uppercase tracking-[0.1em]">{visualTexts[i]}</span>
                  </div>
                </div>
              </motion.div>
              );
            })}
          </div>
        </section>

        {/* 6. Testimonials */}
        <section className="py-24 lg:py-40">
          <motion.div 
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true, margin: "-100px" }}
            variants={fadeUp}
            className="flex flex-col items-center text-center max-w-[800px] mx-auto mb-16 sm:mb-20"
          >
            <h2 className="text-[clamp(36px,6vw,64px)] font-black leading-[0.96] tracking-[-0.05em]">Loved by students.</h2>
          </motion.div>

          <div className="grid md:grid-cols-3 gap-6">
            {testimonials.map((t, i) => (
              <motion.div
                key={t.name}
                initial={{ opacity: 0, y: 40, filter: 'blur(8px)' }}
                whileInView={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
                transition={{ delay: i * 0.15, duration: 1.2, ease: [0.16, 1, 0.3, 1] }}
                viewport={{ once: true }}
                className="rounded-[2rem] sm:rounded-[2.5rem] bg-black p-1.5 sm:p-2 shadow-[0_40px_80px_rgba(0,0,0,0.15)]"
              >
                <div className="h-full w-full rounded-[calc(2rem-0.5rem)] sm:rounded-[calc(2.5rem-0.5rem)] bg-[#171717] border border-white/5 p-6 sm:p-10 flex flex-col">
                  <div className="flex gap-1 mb-6 sm:mb-8">
                    {[...Array(t.rating)].map((_, idx) => (
                      <Star key={idx} className="h-4 w-4 fill-[#FFE071] text-[#FFE071]" />
                    ))}
                  </div>
                  <p className="text-[15px] sm:text-[17px] font-medium leading-relaxed text-white/90 mb-8 sm:mb-10">&ldquo;{t.content}&rdquo;</p>
                  <div className="flex items-center gap-4 mt-auto">
                    {/* 
                      IMAGE PLACEHOLDER — Student profile photo
                      Recommended image: Realistic student portrait headshot, diverse representation.
                      Format: 1:1 square, JPG/webp, ~120×120px. Should match the student's name and role.
                    */}
                    <div className="h-10 w-10 sm:h-12 sm:w-12 rounded-full bg-gradient-to-br from-[#FFD8CD] to-[#F6B39F] flex items-center justify-center font-black text-white text-xs sm:text-sm shadow-[inset_0_1px_0_rgba(255,255,255,0.3)]">
                      {t.name.charAt(0)}
                    </div>
                    <div>
                      <h4 className="font-bold text-[14px] sm:text-[15px] text-white">{t.name}</h4>
                      <p className="text-[12px] sm:text-[13px] font-medium text-white/50">{t.role}</p>
                    </div>
                  </div>
                </div>
              </motion.div>
            ))}
          </div>
        </section>

        {/* 7. Tools & Integrations */}
        <section className="py-24 lg:py-40 overflow-hidden" id="integrations">
          <motion.div
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true, margin: "-100px" }}
            variants={fadeUp}
          >
            <div className="text-center mb-12 sm:mb-16">
              <span className="rounded-full bg-black/5 px-4 py-1.5 text-[10px] sm:text-[11px] font-black uppercase tracking-[0.2em] text-[#74736D]">Integrations</span>
              <h2 className="text-[clamp(28px,5vw,48px)] font-black leading-[0.96] tracking-[-0.05em] mt-6">Works where you study.</h2>
            </div>
          </motion.div>
          
          <div className="relative w-full overflow-hidden">
            {/* 
              LOGO PLACEHOLDER — Integration partner logos
              Replace with official SVG logos from Simple Icons CDN or brand assets.
              Suggested CDN: https://cdn.simpleicons.org/whatsapp/171717 for WhatsApp, etc.
              Format: SVG single-color (currentColor #74736D / #171717), ~32px icons + brand name.
            */}
            <div className="flex gap-8 sm:gap-16 items-center flex-wrap justify-center opacity-40 hover:opacity-70 transition-all duration-700">
              <div className="flex flex-col items-center gap-2 group">
                <div className="w-12 h-12 rounded-[1rem] bg-[#25D366]/10 flex items-center justify-center transition-all duration-500 group-hover:scale-110 group-hover:bg-[#25D366]/20">
                  <MessageCircle className="h-6 w-6 text-[#25D366]" />
                </div>
                <span className="text-[10px] font-black tracking-[-0.01em] text-[#74736D]">WhatsApp</span>
              </div>
              <div className="flex flex-col items-center gap-2 group">
                <div className="w-12 h-12 rounded-[1rem] bg-[#4A154B]/10 flex items-center justify-center transition-all duration-500 group-hover:scale-110 group-hover:bg-[#4A154B]/20">
                  <Zap className="h-6 w-6 text-[#4A154B]" />
                </div>
                <span className="text-[10px] font-black tracking-[-0.01em] text-[#74736D]">Slack</span>
              </div>
              <div className="flex flex-col items-center gap-2 group">
                <div className="w-12 h-12 rounded-[1rem] bg-[#E72429]/10 flex items-center justify-center transition-all duration-500 group-hover:scale-110 group-hover:bg-[#E72429]/20">
                  <BookOpen className="h-6 w-6 text-[#E72429]" />
                </div>
                <span className="text-[10px] font-black tracking-[-0.01em] text-[#74736D]">Canvas</span>
              </div>
              <div className="flex flex-col items-center gap-2 group">
                <div className="w-12 h-12 rounded-[1rem] bg-black/5 flex items-center justify-center transition-all duration-500 group-hover:scale-110 group-hover:bg-black/10">
                  <FileText className="h-6 w-6 text-[#171717]" />
                </div>
                <span className="text-[10px] font-black tracking-[-0.01em] text-[#74736D]">Notion</span>
              </div>
              <div className="flex flex-col items-center gap-2 group">
                <div className="w-12 h-12 rounded-[1rem] bg-[#4285F4]/10 flex items-center justify-center transition-all duration-500 group-hover:scale-110 group-hover:bg-[#4285F4]/20">
                  <CalendarDays className="h-6 w-6 text-[#4285F4]" />
                </div>
                <span className="text-[10px] font-black tracking-[-0.01em] text-[#74736D]">Google Calendar</span>
              </div>
            </div>
          </div>
        </section>

        {/* 8. Pricing Section */}
        <section className="py-24 lg:py-40" id="pricing">
          <motion.div 
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true, margin: "-100px" }}
            variants={fadeUp}
            className="flex flex-col items-center text-center max-w-[800px] mx-auto mb-16 sm:mb-20"
          >
            <h2 className="text-[clamp(36px,6vw,64px)] font-black leading-[0.96] tracking-[-0.05em]">Pricing</h2>
          </motion.div>

          <div className="grid md:grid-cols-2 gap-8 max-w-[900px] mx-auto">
            {/* Free Plan */}
            <motion.div 
              initial={{ opacity: 0, x: -20, filter: 'blur(8px)' }}
              whileInView={{ opacity: 1, x: 0, filter: 'blur(0px)' }}
              viewport={{ once: true }}
              transition={{ duration: 1.2, ease: [0.16, 1, 0.3, 1] }}
              className="rounded-[2rem] sm:rounded-[3rem] bg-black/[0.02] p-1.5 sm:p-2 border border-black/[0.04]"
            >
              <div className="h-full w-full rounded-[calc(2rem-0.5rem)] sm:rounded-[calc(3rem-0.5rem)] bg-white p-8 sm:p-12 shadow-sm flex flex-col">
                <h3 className="text-2xl sm:text-3xl font-black mb-2">Basic</h3>
                <div className="flex items-baseline gap-1 mb-8 sm:mb-10">
                  <span className="text-5xl sm:text-6xl font-black">$0</span>
                  <span className="text-[15px] sm:text-[17px] text-[#74736D] font-medium">/month</span>
                </div>
                <ul className="space-y-4 sm:space-y-5 mb-10 sm:mb-12 flex-1">
                  <li className="flex items-center gap-3 sm:gap-4 text-[15px] sm:text-[16px] font-medium text-[#5F5F59]"><Check className="h-5 w-5 sm:h-6 sm:w-6 text-[#1C8D5A]" /> 3 Course Groups</li>
                  <li className="flex items-center gap-3 sm:gap-4 text-[15px] sm:text-[16px] font-medium text-[#5F5F59]"><Check className="h-5 w-5 sm:h-6 sm:w-6 text-[#1C8D5A]" /> AI Deadline Extraction</li>
                  <li className="flex items-center gap-3 sm:gap-4 text-[15px] sm:text-[16px] font-medium text-[#5F5F59]"><Check className="h-5 w-5 sm:h-6 sm:w-6 text-[#1C8D5A]" /> Basic Calendar Sync</li>
                </ul>
                <Link href="/register" className="group flex min-h-[56px] sm:min-h-[64px] items-center justify-between gap-4 rounded-full border-2 border-black/5 bg-transparent pl-6 sm:pl-8 pr-1.5 sm:pr-2 py-1.5 sm:py-2 text-[15px] sm:text-[17px] font-bold text-[#171717] transition-all duration-500 ease-[cubic-bezier(0.16,1,0.3,1)] hover:bg-black/5 active:scale-[0.98]">
                  Get Started
                  <span className="grid h-10 w-10 sm:h-12 sm:w-12 place-items-center rounded-full bg-white shadow-sm transition-all duration-500 ease-[cubic-bezier(0.16,1,0.3,1)] group-hover:scale-105 group-hover:translate-x-1">
                    <ArrowRight className="h-4 w-4 sm:h-5 sm:w-5" />
                  </span>
                </Link>
              </div>
            </motion.div>

            {/* Pro Plan */}
            <motion.div 
              initial={{ opacity: 0, x: 20, filter: 'blur(8px)' }}
              whileInView={{ opacity: 1, x: 0, filter: 'blur(0px)' }}
              viewport={{ once: true }}
              transition={{ duration: 1.2, ease: [0.16, 1, 0.3, 1] }}
              className="rounded-[2rem] sm:rounded-[3rem] bg-[#FF5A36] p-1.5 sm:p-2 shadow-[0_32px_64px_rgba(255,90,54,0.2)] relative"
            >
              <div className="absolute -top-3 sm:-top-4 left-1/2 -translate-x-1/2 bg-[#171717] text-white px-4 sm:px-5 py-1.5 sm:py-2 rounded-full text-[10px] sm:text-[11px] font-black uppercase tracking-[0.2em] shadow-lg z-10 whitespace-nowrap">
                Most Popular
              </div>
              <div className="h-full w-full rounded-[calc(2rem-0.5rem)] sm:rounded-[calc(3rem-0.5rem)] bg-gradient-to-b from-[#FFF0EB] to-white p-8 sm:p-12 flex flex-col shadow-[inset_0_1px_1px_rgba(255,255,255,1)]">
                <h3 className="text-2xl sm:text-3xl font-black mb-2 text-[#D93A1C]">Pro</h3>
                <div className="flex items-baseline gap-1 mb-8 sm:mb-10">
                  <span className="text-5xl sm:text-6xl font-black">$4</span>
                  <span className="text-[15px] sm:text-[17px] text-[#74736D] font-medium">/month</span>
                </div>
                <ul className="space-y-4 sm:space-y-5 mb-10 sm:mb-12 flex-1">
                  <li className="flex items-center gap-3 sm:gap-4 text-[15px] sm:text-[16px] font-bold"><Check className="h-5 w-5 sm:h-6 sm:w-6 text-[#FF5A36]" /> Unlimited Groups</li>
                  <li className="flex items-center gap-3 sm:gap-4 text-[15px] sm:text-[16px] font-bold"><Check className="h-5 w-5 sm:h-6 sm:w-6 text-[#FF5A36]" /> Advanced AI Insights</li>
                  <li className="flex items-center gap-3 sm:gap-4 text-[15px] sm:text-[16px] font-bold"><Check className="h-5 w-5 sm:h-6 sm:w-6 text-[#FF5A36]" /> Notion Integration</li>
                  <li className="flex items-center gap-3 sm:gap-4 text-[15px] sm:text-[16px] font-bold"><Check className="h-5 w-5 sm:h-6 sm:w-6 text-[#FF5A36]" /> Priority Support</li>
                </ul>
                <Link href="/register" className="group flex min-h-[56px] sm:min-h-[64px] items-center justify-between gap-4 rounded-full bg-[#FF5A36] pl-6 sm:pl-8 pr-1.5 sm:pr-2 py-1.5 sm:py-2 text-[15px] sm:text-[17px] font-bold text-white shadow-[0_16px_32px_rgba(255,90,54,0.3)] transition-all duration-500 ease-[cubic-bezier(0.16,1,0.3,1)] hover:shadow-[0_24px_48px_rgba(255,90,54,0.4)] active:scale-[0.98]">
                  Upgrade to Pro
                  <span className="grid h-10 w-10 sm:h-12 sm:w-12 place-items-center rounded-full bg-white/20 transition-all duration-500 ease-[cubic-bezier(0.16,1,0.3,1)] group-hover:scale-105 group-hover:bg-white/30 group-hover:translate-x-1">
                    <ArrowRight className="h-4 w-4 sm:h-5 sm:w-5" />
                  </span>
                </Link>
              </div>
            </motion.div>
          </div>
        </section>

        {/* 9. FAQ */}
        <section className="py-24 lg:py-40" id="faq">
          <motion.div 
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true, margin: "-100px" }}
            variants={fadeUp}
            className="grid lg:grid-cols-[1fr_1.5fr] gap-10 sm:gap-16 max-w-[1000px] mx-auto"
          >
            <div>
              <span className="mb-4 sm:mb-6 inline-block rounded-full bg-black/5 px-4 py-1.5 text-[10px] sm:text-[11px] font-black uppercase tracking-[0.2em] text-[#74736D]">FAQ</span>
              <h2 className="text-[clamp(36px,6vw,64px)] font-black leading-[0.96] tracking-[-0.05em] mb-4 sm:mb-6">Got questions?</h2>
              <p className="text-[17px] sm:text-[19px] font-medium leading-relaxed text-[#5F5F59] mb-8 sm:mb-12">Have questions? We&rsquo;ve got answers.</p>
            </div>
            
            <div className="rounded-[2rem] sm:rounded-[2.5rem] bg-black/[0.02] p-1.5 sm:p-2 border border-black/[0.04]">
              <div className="rounded-[calc(2rem-0.5rem)] sm:rounded-[calc(2.5rem-0.5rem)] bg-white p-6 sm:p-12 shadow-sm">
                {faqs.map((faq, index) => (
                  <FAQItem key={index} question={faq.question} answer={faq.answer} />
                ))}
              </div>
            </div>
          </motion.div>
        </section>

        {/* 10. Final CTA */}
        <section className="py-24 lg:py-40">
          <motion.div
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true, margin: "-100px" }}
            variants={fadeUpScale}
            className="relative mx-auto max-w-[1100px] overflow-hidden rounded-[2.5rem] sm:rounded-[3.5rem] bg-[#171717] p-10 sm:p-16 lg:p-24 text-center shadow-[0_40px_100px_rgba(30,30,30,0.25)]"
          >
            {/* Ambient glow */}
            <div className="pointer-events-none absolute inset-0">
              <div className="absolute -top-24 left-1/2 -translate-x-1/2 h-[320px] w-[620px] rounded-full bg-[radial-gradient(closest-side,rgba(255,90,54,0.35),transparent_70%)] blur-3xl" />
              <div className="absolute bottom-0 right-0 h-[260px] w-[420px] rounded-full bg-[radial-gradient(closest-side,rgba(124,107,224,0.18),transparent_70%)] blur-3xl" />
            </div>

            <div className="relative z-10 flex flex-col items-center">
              <span className="mb-6 sm:mb-8 inline-flex items-center rounded-full border border-white/10 bg-white/5 px-4 py-1.5 text-[10px] sm:text-[11px] font-black uppercase tracking-[0.2em] text-[#FFD8CD] backdrop-blur-md">
                <span className="mr-2 h-1.5 w-1.5 rounded-full bg-[#FF5A36] animate-pulse" />
                Start in under 60 seconds
              </span>
              <h2 className="max-w-[760px] text-[clamp(34px,6vw,68px)] font-black leading-[0.95] tracking-[-0.05em] text-white">
                Stop scrolling. Start <span className="text-transparent bg-clip-text bg-gradient-to-br from-[#FF8A66] to-[#FF4B24]">catching up</span>.
              </h2>
              <p className="mt-5 sm:mt-7 max-w-[520px] text-[16px] sm:text-[19px] font-medium leading-relaxed text-white/60">
                Connect one group today. Get your first briefing tonight. Free for most students — no card required.
              </p>
              <div className="mt-8 sm:mt-12 flex flex-col items-stretch gap-3 sm:flex-row sm:items-center sm:gap-4">
                <Link href="/register" className="group flex min-h-[56px] sm:min-h-[64px] items-center justify-between sm:justify-start gap-4 rounded-full bg-[#FF5A36] pl-8 pr-2 py-2 text-[16px] sm:text-[17px] font-bold text-white shadow-[0_16px_40px_rgba(255,90,54,0.4)] transition-all duration-500 ease-[cubic-bezier(0.16,1,0.3,1)] active:scale-[0.97] hover:shadow-[0_24px_50px_rgba(255,90,54,0.5)]">
                  Start for Free
                  <span className="grid h-10 w-10 sm:h-12 sm:w-12 place-items-center rounded-full bg-white/20 transition-all duration-500 ease-[cubic-bezier(0.16,1,0.3,1)] group-hover:scale-105 group-hover:bg-white/30 group-hover:translate-x-1">
                    <ArrowRight className="h-4 w-4 sm:h-5 sm:w-5" />
                  </span>
                </Link>
                <Link href="/login" className="flex min-h-[56px] sm:min-h-[64px] items-center justify-center rounded-full border border-white/15 px-8 text-[15px] sm:text-[16px] font-bold text-white/80 transition-colors hover:bg-white/5 hover:text-white">
                  Talk to the team
                </Link>
              </div>
              <p className="mt-6 sm:mt-8 flex items-center gap-2 text-[12px] sm:text-[13px] font-medium text-white/40">
                <CheckCircle2 className="h-4 w-4 text-[#1C8D5A]" />
                Free forever for 3 course groups · Cancel anytime
              </p>
            </div>
          </motion.div>
        </section>

        {/* 11. Footer */}
        <footer className="mt-12 sm:mt-20 flex flex-col gap-10 sm:gap-12 border-t border-[#F0F0ED] py-12 sm:py-20">
          <div className="flex flex-col lg:flex-row justify-between gap-12 sm:gap-16">
            <div className="max-w-[360px]">
              <Link href="/" className="flex items-center gap-3 sm:gap-4 mb-6 sm:mb-8 transition-transform hover:scale-105 active:scale-95 w-max">
                <div className="relative flex h-8 w-8 sm:h-10 sm:w-10 items-center justify-center overflow-hidden rounded-[10px] sm:rounded-[12px] bg-[#171717] text-[#F0EAD6]">
                  <AppLogo className="w-4 h-4 sm:w-5 sm:h-5" />
                </div>
                <span className="text-xl sm:text-2xl font-black tracking-[-0.04em]">Knowtis</span>
              </Link>
              <p className="text-[15px] sm:text-[16px] font-medium text-[#74736D] leading-relaxed">
                Built for students who would rather learn than scroll. Follow along and turn the chaos into a clean week.
              </p>
            </div>
            
            <div className="grid grid-cols-2 md:grid-cols-3 gap-10 sm:gap-12 lg:gap-20">
              <div className="flex flex-col gap-4 sm:gap-5">
                <h5 className="font-black text-[#171717] text-[13px] sm:text-[15px] uppercase tracking-[0.1em]">Product</h5>
                <Link href="#features" className="text-[15px] sm:text-[16px] font-medium text-[#74736D] hover:text-[#FF5A36] transition-colors">Features</Link>
                <Link href="#pricing" className="text-[15px] sm:text-[16px] font-medium text-[#74736D] hover:text-[#FF5A36] transition-colors">Pricing</Link>
                <Link href="#integrations" className="text-[15px] sm:text-[16px] font-medium text-[#74736D] hover:text-[#FF5A36] transition-colors">Integrations</Link>
              </div>
              <div className="flex flex-col gap-4 sm:gap-5">
                <h5 className="font-black text-[#171717] text-[13px] sm:text-[15px] uppercase tracking-[0.1em]">Legal</h5>
                <Link href="#" className="text-[15px] sm:text-[16px] font-medium text-[#74736D] hover:text-[#FF5A36] transition-colors">Privacy Policy</Link>
                <Link href="#" className="text-[15px] sm:text-[16px] font-medium text-[#74736D] hover:text-[#FF5A36] transition-colors">Terms of Service</Link>
              </div>
              <div className="flex flex-col gap-4 sm:gap-5">
                <h5 className="font-black text-[#171717] text-[13px] sm:text-[15px] uppercase tracking-[0.1em]">Stay in touch</h5>
                <Link href="mailto:hello@knowtis.app" className="text-[15px] sm:text-[16px] font-medium text-[#74736D] hover:text-[#FF5A36] transition-colors">hello@knowtis.app</Link>
                <Link href="#" className="text-[15px] sm:text-[16px] font-medium text-[#74736D] hover:text-[#FF5A36] transition-colors">Twitter</Link>
                <Link href="#" className="text-[15px] sm:text-[16px] font-medium text-[#74736D] hover:text-[#FF5A36] transition-colors">Instagram</Link>
                <Link href="#" className="text-[15px] sm:text-[16px] font-medium text-[#74736D] hover:text-[#FF5A36] transition-colors">Discord</Link>
              </div>
            </div>
          </div>
          
          <div className="pt-8 sm:pt-10 border-t border-[#F0F0ED] flex flex-col sm:flex-row justify-between items-center gap-4 sm:gap-6 text-[14px] sm:text-[15px] font-medium text-[#A3A29C]">
            <p>© {new Date().getFullYear()} Knowtis. All rights reserved.</p>
            <div className="flex items-center gap-2">
              <span className="h-2 w-2 rounded-full bg-[#1C8D5A] animate-pulse" />
              Systems operational
            </div>
          </div>
        </footer>
      </div>
    </main>
  );
}

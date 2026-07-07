'use client';

import Link from 'next/link';
import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  ArrowRight, 
  MessageCircle, 
  Check, 
  Sparkles, 
  Bell, 
  CalendarDays, 
  VolumeX, 
  ShieldCheck, 
  Clock, 
  Image as ImageIcon,
  RotateCcw,
  Zap,
  Info,
  ChevronLeft,
  ChevronRight,
  ArrowLeft,
  Lock,
  Calendar
} from 'lucide-react';
import { GOOGLE_OAUTH_URL } from '@/lib/api';
import { useAppStore } from '@/lib/store';

function GoogleIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
      <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
      <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
      <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/>
      <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
    </svg>
  );
}

function AppleIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
      <path d="M18.71 19.5c-.83 1.24-1.71 2.45-3.05 2.47-1.34.03-1.77-.79-3.29-.79-1.53 0-2 .77-3.27.82-1.31.05-2.3-1.32-3.14-2.53C4.25 17 2.94 12.45 4.7 9.39c.87-1.52 2.43-2.48 4.12-2.51 1.28-.02 2.5.87 3.29.87.78 0 2.26-1.07 3.81-.91.65.03 2.47.26 3.64 1.98-.09.06-2.17 1.28-2.15 3.81.03 3.02 2.65 4.03 2.68 4.04-.03.07-.42 1.44-1.38 2.83M15.97 4.17c.66-.81 1.11-1.93.99-3.06-.96.04-2.13.64-2.82 1.45-.6.69-1.12 1.84-.98 2.94.1.08.2.1.29.1 1 .01 2.2-.62 2.52-1.43z"/>
    </svg>
  );
}

const TOTAL_SLIDES_DESKTOP = 6;
const TOTAL_SLIDES_MOBILE = 5;

export default function OnboardingPage() {
  const router = useRouter();
  const isAuthenticated = useAppStore((s) => s.isAuthenticated);
  const user = useAppStore((s) => s.user);
  const [isMobile, setIsMobile] = useState<boolean | null>(null);
  const [currentSlide, setCurrentSlide] = useState(0);
  const [direction, setDirection] = useState(1); // 1 = forward, -1 = backward
  const [isLinking, setIsLinking] = useState(false);
  const [chatMessages, setChatMessages] = useState<Array<{ id: number; sender: string; text: string; role: string; time: string; isSignal?: boolean }>>([]);
  const [showScan, setShowScan] = useState(false);
  const [scanFinished, setScanFinished] = useState(false);

  useEffect(() => {
    const token = window.localStorage.getItem('knowtis_token');
    if (!token) return;

    const onboarded = window.localStorage.getItem('knowtis_onboarded') === 'true';
    router.replace(onboarded ? '/dashboard' : '/onboarding/research');
  }, [router]);

  // Dynamic Viewport Check
  useEffect(() => {
    const checkMobile = () => {
      setIsMobile(window.innerWidth < 1024);
    };
    checkMobile();
    window.addEventListener('resize', checkMobile);
    return () => window.removeEventListener('resize', checkMobile);
  }, []);

  // Sync / Reset slide states when changing screen modes
  useEffect(() => {
    if (isMobile === null) return;

    setCurrentSlide(0);
    setDirection(1);
    setChatMessages([]);
    setShowScan(false);
    setScanFinished(false);
  }, [isMobile]);

  // Helper to change slides with direction
  const goToSlide = useCallback((targetSlide: number) => {
    const total = isMobile ? TOTAL_SLIDES_MOBILE : TOTAL_SLIDES_DESKTOP;
    if (targetSlide < 0 || targetSlide >= total) return;
    setDirection(targetSlide > currentSlide ? 1 : -1);
    setCurrentSlide(targetSlide);
  }, [currentSlide, isMobile]);

  const handleNext = useCallback(() => {
    const total = isMobile ? TOTAL_SLIDES_MOBILE : TOTAL_SLIDES_DESKTOP;
    if (currentSlide < total - 1) {
      goToSlide(currentSlide + 1);
    }
  }, [currentSlide, goToSlide, isMobile]);

  const handleBack = useCallback(() => {
    if (currentSlide > 0) {
      goToSlide(currentSlide - 1);
    }
  }, [currentSlide, goToSlide]);

  // Keyboard navigation
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'ArrowRight') handleNext();
      if (e.key === 'ArrowLeft') handleBack();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleNext, handleBack]);

  // Desktop Ingestion sequence (Slide 1)
  useEffect(() => {
    if (isMobile !== false || currentSlide !== 1) {
      setChatMessages([]);
      setShowScan(false);
      setScanFinished(false);
      return;
    }

    const messages = [
      { id: 1, sender: 'Tobi', text: 'Yo, has the lecturer entered?', role: 'student', time: '10:02 AM' },
      { id: 2, sender: 'Amara', text: 'Nah, still waiting. Probably got caught in traffic.', role: 'student', time: '10:03 AM' },
      { id: 3, sender: 'Tobi', text: '😂 Typical. I might just grab coffee.', role: 'student', time: '10:03 AM' },
      { 
        id: 4, 
        sender: 'Dr. Helen (PHY 301)', 
        text: '🚨 NOTICE: Today\'s Lecture and the Physics 301 Lab Quiz have been rescheduled to Thursday at 2:00 PM in Lab Hall C. The deadline for Lab Report 2 is also extended to Thursday 4:00 PM.', 
        role: 'lecturer', 
        time: '10:05 AM',
        isSignal: true 
      },
      { id: 5, sender: 'Chinedu', text: 'Wait, did she say Thursday 2pm or 4pm?', role: 'student', time: '10:06 AM' },
      { id: 6, sender: 'Amara', text: 'Quiz is Thursday 2pm, Report is 4pm.', role: 'student', time: '10:06 AM' },
    ];

    let currentMsgIndex = 0;
    const interval = setInterval(() => {
      if (currentMsgIndex < messages.length) {
        setChatMessages(prev => [...prev, messages[currentMsgIndex]]);
        currentMsgIndex++;
      } else {
        clearInterval(interval);
        setTimeout(() => setShowScan(true), 800);
      }
    }, 800);

    return () => clearInterval(interval);
  }, [currentSlide, isMobile]);

  // Desktop Scan sequence (Slide 1)
  useEffect(() => {
    if (isMobile !== false || !showScan || currentSlide !== 1) return;

    const timer = setTimeout(() => {
      setScanFinished(true);
      setTimeout(() => {
        setDirection(1);
        setCurrentSlide(2);
      }, 1500);
    }, 2800);

    return () => clearTimeout(timer);
  }, [showScan, currentSlide, isMobile]);

  const handleLinkSimulation = () => {
    setIsLinking(true);
    setTimeout(() => {
      setIsLinking(false);
      setDirection(1);
      setCurrentSlide(1);
    }, 1500);
  };

  const resetSimulation = () => {
    setDirection(-1);
    setCurrentSlide(0);
    setChatMessages([]);
    setShowScan(false);
    setScanFinished(false);
  };

  // Shared Animation Variants
  const slideVariants = {
    enter: (dir: number) => ({
      x: dir > 0 ? 300 : -300,
      opacity: 0,
      filter: 'blur(8px)',
    }),
    center: {
      x: 0,
      opacity: 1,
      filter: 'blur(0px)',
      transition: {
        x: { type: 'spring' as const, stiffness: 300, damping: 30 },
        opacity: { duration: 0.3 },
        filter: { duration: 0.3 }
      }
    },
    exit: (dir: number) => ({
      x: dir < 0 ? 300 : -300,
      opacity: 0,
      filter: 'blur(8px)',
      transition: {
        x: { type: 'spring' as const, stiffness: 300, damping: 30 },
        opacity: { duration: 0.25 },
        filter: { duration: 0.25 }
      }
    }),
  };

  if (isMobile === null) {
    return <main className="min-h-dvh bg-[#FBFBFA]" />;
  }

  // --- MOBILE VIEWS RENDERER ---
  if (isMobile) {
    // Dynamic premium backgrounds
    const bgGradients = [
      'from-[#E2F5F0] via-[#F4FAF8] to-[#FBFBFA]', // Minty Green
      'from-[#FFF0EC] via-[#FFF8F6] to-[#FBFBFA]', // Peach/Coral
      'from-[#E8F1FC] via-[#F3F7FD] to-[#FBFBFA]', // Sky Blue
      'from-[#FFFCE6] via-[#FFFEFA] to-[#FBFBFA]', // Light Yellow
      'from-[#EFEFFE] via-[#F9F9FF] to-[#FBFBFA]'  // Light Lavender
    ];

    return (
      <main className={`relative min-h-dvh flex flex-col justify-between overflow-hidden bg-gradient-to-b ${bgGradients[currentSlide]} text-[#171717] font-sans pb-6 transition-all duration-700 ease-out`}>
        
        {/* Header (Top Right Skip) */}
        <header className="w-full px-6 pt-6 flex justify-end shrink-0 z-10">
          {currentSlide < TOTAL_SLIDES_MOBILE - 1 && (
            <button 
              onClick={() => goToSlide(TOTAL_SLIDES_MOBILE - 1)}
              className="text-xs font-black uppercase tracking-wider text-[#A3A29C] hover:text-[#171717] transition-colors"
            >
              Skip
            </button>
          )}
        </header>

        {/* Content Area */}
        <div className="flex-1 flex flex-col justify-center px-6">
          <AnimatePresence initial={false} custom={direction} mode="wait">
            <motion.div
              key={currentSlide}
              custom={direction}
              variants={slideVariants}
              initial="enter"
              animate="center"
              exit="exit"
              className="flex flex-col items-center"
            >
              {/* GLASSMORPHIC VISUAL CARDS FOR SLIDES */}
              <div className="mb-10 flex justify-center w-full relative">
                
                {/* Visual 0: The WhatsApp Noise */}
                {currentSlide === 0 && (
                  <div className="relative w-48 h-48 rounded-[2.5rem] bg-white/60 border border-white/80 shadow-[0_20px_40px_rgba(0,0,0,0.06)] backdrop-blur-md flex items-center justify-center overflow-visible">
                    <motion.div 
                      animate={{ scale: [1, 1.06, 1] }} 
                      transition={{ duration: 3, repeat: Infinity }}
                      className="w-14 h-14 rounded-full bg-[#EAF8F0] border-2 border-[#32B87B] flex items-center justify-center text-[#32B87B]"
                    >
                      <MessageCircle className="w-7 h-7 fill-[#32B87B]/10" />
                    </motion.div>
                    
                    {/* Floating noise tags */}
                    <motion.span 
                      animate={{ y: [0, -5, 0] }} transition={{ duration: 2, repeat: Infinity }}
                      className="absolute top-6 left-1 bg-white/80 border border-[#E9E9E6] text-[10px] font-bold text-[#74736D] px-2.5 py-0.5 rounded-full shadow-sm"
                    >
                      Meme 🐸
                    </motion.span>
                    <motion.span 
                      animate={{ y: [0, 4, 0] }} transition={{ duration: 2.5, repeat: Infinity, delay: 0.2 }}
                      className="absolute top-10 right-2 bg-white/80 border border-[#E9E9E6] text-[10px] font-bold text-[#74736D] px-2.5 py-0.5 rounded-full shadow-sm"
                    >
                      LOL 😂
                    </motion.span>
                    <motion.span 
                      animate={{ y: [0, -3, 0] }} transition={{ duration: 2.2, repeat: Infinity, delay: 0.4 }}
                      className="absolute bottom-16 -right-2 bg-white/80 border border-[#E9E9E6] text-[10px] font-bold text-[#74736D] px-2.5 py-0.5 rounded-full shadow-sm"
                    >
                      Who has notes?
                    </motion.span>
                    <motion.span 
                      animate={{ y: [0, 5, 0] }} transition={{ duration: 2.8, repeat: Infinity, delay: 0.6 }}
                      className="absolute bottom-12 -left-3 bg-white/80 border border-[#E9E9E6] text-[10px] font-bold text-[#74736D] px-2.5 py-0.5 rounded-full shadow-sm"
                    >
                      Same?
                    </motion.span>
                    <motion.span 
                      animate={{ scale: [1, 1.05, 1], y: [0, -4, 0] }} transition={{ duration: 2.4, repeat: Infinity, delay: 0.1 }}
                      className="absolute -bottom-2 left-1/4 bg-[#FFF0EB] border border-[#FF5A36]/30 text-[10px] font-black text-[#FF5A36] px-3 py-1 rounded-full shadow-md"
                    >
                      Deadline? 🚨
                    </motion.span>
                    
                    {/* Warning badge */}
                    <motion.div 
                      animate={{ scale: [1, 1.15, 1] }}
                      transition={{ duration: 2, repeat: Infinity }}
                      className="absolute -top-3 -right-3 w-9 h-9 rounded-full bg-[#FF5A36] flex items-center justify-center text-white font-black text-lg shadow-[0_8px_16px_rgba(255,90,54,0.3)]"
                    >
                      !
                    </motion.div>
                  </div>
                )}

                {/* Visual 1: AI Filter */}
                {currentSlide === 1 && (
                  <div className="relative w-48 h-48 rounded-[2.5rem] bg-white/60 border border-white/80 shadow-[0_20px_40px_rgba(0,0,0,0.06)] backdrop-blur-md flex flex-col justify-center p-4 overflow-hidden">
                    
                    {/* Static messy chat list */}
                    <div className="space-y-1.5 opacity-40 blur-[0.6px] transition-all">
                      <div className="bg-[#E9E9E6] rounded-lg p-1.5 text-[8px] font-bold text-[#74736D] w-3/4 ml-auto">
                        Lol did u guys do the physics homework yet?
                      </div>
                      <div className="bg-[#E9E9E6] rounded-lg p-1.5 text-[8px] font-bold text-[#74736D] w-1/2 ml-auto">
                        Nah, too busy playing FIFA 😂
                      </div>
                    </div>

                    {/* Target signal box */}
                    <motion.div 
                      initial={{ scale: 0.95, opacity: 0 }}
                      animate={{ scale: 1, opacity: 1 }}
                      transition={{ delay: 0.3 }}
                      className="my-3 bg-[#EAF8F0] border-2 border-[#32B87B] rounded-2xl p-2.5 shadow-sm text-left relative"
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-[7.5px] font-black text-[#32B87B] uppercase tracking-wider">PHY 301 · Lecturer Alert</span>
                        <div className="w-3.5 h-3.5 rounded-full bg-[#32B87B] flex items-center justify-center text-white">
                          <Check className="w-2.5 h-2.5" strokeWidth={3} />
                        </div>
                      </div>
                      <p className="text-[9px] font-black leading-tight text-slate-800">
                        Lab report extension until Thursday 4pm. Lab quiz is Thursday 2pm.
                      </p>
                    </motion.div>

                    {/* Scan Line Laser */}
                    <motion.div
                      animate={{ top: ['0%', '100%', '0%'] }}
                      transition={{ duration: 3, repeat: Infinity, ease: 'easeInOut' }}
                      className="absolute inset-x-0 h-0.5 bg-gradient-to-r from-transparent via-[#32B87B] to-transparent shadow-[0_0_8px_#32B87B] pointer-events-none z-10"
                    />
                  </div>
                )}

                {/* Visual 2: Connect Invite Link */}
                {currentSlide === 2 && (
                  <div className="relative w-48 h-48 rounded-[2.5rem] bg-white/60 border border-white/80 shadow-[0_20px_40px_rgba(0,0,0,0.06)] backdrop-blur-md flex flex-col justify-between p-5 overflow-visible">
                    
                    {/* Simulated input slot */}
                    <div className="space-y-1.5 text-left">
                      <span className="text-[8px] font-black text-[#9A9A94] uppercase tracking-wider pl-1">Link Class WhatsApp</span>
                      <div className="bg-white border border-[#E9E9E6] rounded-xl py-2 px-3 flex items-center justify-between shadow-sm">
                        <span className="text-[9px] font-bold text-slate-400 truncate w-32">chat.whatsapp.com/invite/Kj9s...</span>
                        <span className="w-1.5 h-1.5 rounded-full bg-[#32B87B] animate-ping" />
                      </div>
                    </div>

                    {/* Shield icon & secure connection */}
                    <div className="flex items-center gap-3 bg-white/90 border border-white p-2.5 rounded-2xl shadow-sm">
                      <div className="w-8 h-8 rounded-xl bg-blue-50 flex items-center justify-center text-[#4285F4] shrink-0">
                        <Lock className="w-4 h-4" />
                      </div>
                      <div className="text-left min-w-0">
                        <span className="block text-[8px] font-black text-slate-800">Read-Only Safe Listener</span>
                        <span className="block text-[7.5px] font-bold text-slate-400">No DMs or private data accessed.</span>
                      </div>
                    </div>
                  </div>
                )}

                {/* Visual 3: Night Brief Notification */}
                {currentSlide === 3 && (
                  <div className="relative w-48 h-48 rounded-[2.5rem] bg-white/60 border border-white/80 shadow-[0_20px_40px_rgba(0,0,0,0.06)] backdrop-blur-md flex flex-col items-center justify-center p-4">
                    
                    {/* Bell Icon */}
                    <motion.div
                      animate={{ rotate: [-6, 6, -6] }}
                      transition={{ duration: 1.5, repeat: Infinity, ease: 'easeInOut' }}
                      className="w-14 h-14 rounded-full bg-[#FFF5E1] border-2 border-[#F2A53C] flex items-center justify-center text-[#F2A53C] mb-4 shadow-sm"
                    >
                      <Bell className="w-7 h-7 fill-[#F2A53C]/10" />
                    </motion.div>

                    {/* Floating Alert labels */}
                    <span className="absolute top-8 left-3 bg-white/90 border border-[#FFF0EB] text-[9.5px] font-black text-[#FF5A36] px-2.5 py-0.5 rounded-full shadow-sm">Urgent 🚨</span>
                    <span className="absolute bottom-8 right-2 bg-white/90 border border-[#E9E9E6] text-[9.5px] font-bold text-[#74736D] px-2.5 py-0.5 rounded-full shadow-sm">Night Brief 🌙</span>
                  </div>
                )}

                {/* Visual 4: Calendar Sync */}
                {currentSlide === 4 && (
                  <div className="relative w-48 h-48 rounded-[2.5rem] bg-white/60 border border-white/80 shadow-[0_20px_40px_rgba(0,0,0,0.06)] backdrop-blur-md flex flex-col justify-between p-5 overflow-visible">
                    
                    {/* Calendar grid snippet */}
                    <div className="bg-white border border-[#E9E9E6] rounded-2xl p-2.5 shadow-sm space-y-1.5">
                      <div className="flex items-center justify-between border-b border-slate-100 pb-1.5">
                        <span className="text-[9px] font-black text-slate-800">Thursday 16</span>
                        <div className="w-1.5 h-1.5 rounded-full bg-[#FF5A36]" />
                      </div>
                      <div className="bg-[#FFF0EB] border border-[#FFD8CD] rounded-lg p-1.5 text-left">
                        <span className="block text-[8px] font-black text-[#FF5A36] uppercase tracking-wider">PHY 301 · 2:00 PM</span>
                        <span className="block text-[9px] font-black text-slate-800 leading-tight">Physics Lab Quiz</span>
                      </div>
                    </div>

                    {/* Google & Apple badges */}
                    <div className="flex gap-2 justify-center">
                      <span className="bg-white border border-[#E9E9E6] px-3 py-1 rounded-full text-[9px] font-bold text-slate-600 flex items-center gap-1.5 shadow-sm">
                        <GoogleIcon /> Google
                      </span>
                      <span className="bg-white border border-[#E9E9E6] px-3 py-1 rounded-full text-[9px] font-bold text-slate-600 flex items-center gap-1.5 shadow-sm">
                        <AppleIcon /> Apple
                      </span>
                    </div>
                  </div>
                )}

              </div>

              {/* Progress Dots Indicator */}
              <div className="mb-6 flex justify-center gap-1.5">
                {Array.from({ length: TOTAL_SLIDES_MOBILE }).map((_, i) => (
                  <div
                    key={i}
                    className={`h-1.5 rounded-full transition-all duration-300 ${
                      currentSlide === i ? 'w-6 bg-[#171717]' : 'w-1.5 bg-[#171717]/15'
                    }`}
                  />
                ))}
              </div>

              {/* Text Layout (Left-aligned on 0-3, Centered on 4) */}
              <div className={`w-full max-w-[340px] px-1 ${currentSlide === 4 ? 'text-center' : 'text-left'}`}>
                {currentSlide === 0 && (
                  <>
                    <h2 className="text-[28px] font-black tracking-tight leading-[1.1] text-[#171717]">
                      University chats are <span className="bg-[#FF5A36] text-white px-2 py-0.5 rounded-xl inline-block transform -rotate-1 font-black shadow-sm">chaotic noise</span>.
                    </h2>
                    <p className="mt-4 text-[14px] font-semibold leading-relaxed text-[#686862]">
                      Crucial academic announcements from lecturers get buried within minutes under hundreds of student memes, jokes, and repeated questions.
                    </p>
                  </>
                )}

                {currentSlide === 1 && (
                  <>
                    <h2 className="text-[28px] font-black tracking-tight leading-[1.1] text-[#171717]">
                      Knowtis filters out <span className="bg-[#32B87B] text-white px-2 py-0.5 rounded-xl inline-block transform -rotate-1 font-black shadow-sm">the clutter</span>.
                    </h2>
                    <p className="mt-4 text-[14px] font-semibold leading-relaxed text-[#686862]">
                      Our silent AI listener monitors your group chat in real-time, automatically isolating due dates, assignment specs, and timetable changes.
                    </p>
                  </>
                )}

                {currentSlide === 2 && (
                  <>
                    <h2 className="text-[28px] font-black tracking-tight leading-[1.1] text-[#171717]">
                      Connect your class chat <span className="bg-[#4285F4] text-white px-2 py-0.5 rounded-xl inline-block transform -rotate-1 font-black shadow-sm">in seconds</span>.
                    </h2>
                    <p className="mt-4 text-[14px] font-semibold leading-relaxed text-[#686862]">
                      Just paste your group invite link. Knowtis joins silently as an offline read-only watcher—no DMs, no phone numbers shared, no spam.
                    </p>
                  </>
                )}

                {currentSlide === 3 && (
                  <>
                    <h2 className="text-[28px] font-black tracking-tight leading-[1.1] text-[#171717]">
                      Get notified on <span className="bg-[#F2A53C] text-white px-2 py-0.5 rounded-xl inline-block transform -rotate-1 font-black shadow-sm">your terms</span>.
                    </h2>
                    <p className="mt-4 text-[14px] font-semibold leading-relaxed text-[#686862]">
                      Receive priority WhatsApp alerts only when deadlines change, plus a consolidated &quot;Night Brief&quot; summary every evening.
                    </p>
                  </>
                )}

                {currentSlide === 4 && (
                  <>
                    <h2 className="text-[28px] font-black tracking-tight leading-[1.1] text-[#171717]">
                      Your schedule, <span className="bg-[#FF5A36] text-white px-2 py-0.5 rounded-xl inline-block transform -rotate-1 font-black shadow-sm">auto-synced</span>.
                    </h2>
                    <p className="mt-4 text-[14px] font-semibold leading-relaxed text-[#686862] px-2">
                      Every extracted deadline is instantly pushed to your calendar. No more copying dates manually, no more saving screenshots.
                    </p>
                  </>
                )}
              </div>

            </motion.div>
          </AnimatePresence>
        </div>

        {/* Buttons / Controls Area */}
        <div className="shrink-0 w-full max-w-[340px] mx-auto px-6 mt-6 flex flex-col gap-3">
          {currentSlide < 4 ? (
            <div className="flex items-center gap-3">
              {/* Back button */}
              {currentSlide > 0 && (
                <button
                  onClick={handleBack}
                  className="w-12 h-12 rounded-full bg-white border border-[#E9E9E6] shadow-sm flex items-center justify-center text-[#171717] active:scale-95 transition-all shrink-0"
                  aria-label="Back"
                >
                  <ArrowLeft className="w-5 h-5" />
                </button>
              )}
              {/* Continue button */}
              <button
                onClick={handleNext}
                className="flex-1 h-12 bg-[#171717] hover:bg-[#2c2c2c] text-white font-bold rounded-full flex items-center justify-center gap-2 text-sm shadow-[0_8px_16px_rgba(0,0,0,0.1)] active:scale-[0.98] transition-all"
              >
                Continue <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          ) : (
            /* Slide 4 stacked authentication CTAs */
            <div className="flex flex-col gap-2.5 w-full">
              <Link 
                href="/register" 
                className="w-full h-12 bg-[#171717] hover:bg-[#2c2c2c] text-white font-bold rounded-full flex items-center justify-center gap-2 text-sm shadow-[0_8px_16px_rgba(0,0,0,0.1)] active:scale-[0.98] transition-all"
              >
                Start setup <ArrowRight className="w-4 h-4" />
              </Link>
              <a 
                href={GOOGLE_OAUTH_URL} 
                className="w-full h-12 bg-white border border-[#E9E9E6] hover:bg-[#FBFBFA] text-[#171717] font-bold rounded-full flex items-center justify-center gap-2.5 text-sm shadow-sm active:scale-[0.98] transition-all"
              >
                <GoogleIcon />
                Continue with Google
              </a>
              <button 
                className="w-full h-12 bg-white border border-[#E9E9E6] hover:bg-[#FBFBFA] text-[#171717] font-bold rounded-full flex items-center justify-center gap-2.5 text-sm shadow-sm active:scale-[0.98] transition-all"
              >
                <AppleIcon />
                Continue with Apple
              </button>
            </div>
          )}

          {/* Footer Account Status */}
          <div className="text-center mt-3 text-xs font-semibold text-[#686862]">
            {isAuthenticated ? (
              user?.email ? (
                <>
                  Signed in as {user.email.split('@')[0]} · Redirecting
                </>
              ) : (
                <>
                  Already signed in · Redirecting
                </>
              )
            ) : (
              <>
                Already set up?{' '}
                <Link href="/login" className="text-[#FF5A36] hover:underline">Log in</Link>
              </>
            )}
          </div>
        </div>

      </main>
    );
  }

  // --- DESKTOP VIEW RENDERER (Intact) ---
  return (
    <main className="relative min-h-dvh bg-[#FBFBFA] font-sans flex flex-col justify-between overflow-hidden text-[#171717]">
      {/* Background decorations */}
      <div className="absolute inset-0 z-0 pointer-events-none opacity-25 bg-[radial-gradient(#FF5A36_1px,transparent_1px)] [background-size:24px_24px] [mask-image:radial-gradient(ellipse_50%_50%_at_50%_40%,#000_60%,transparent_100%)]" />
      <div className="absolute top-[-10%] left-[-10%] w-[50vw] h-[50vw] rounded-full bg-[#FFE3DB] blur-[120px] opacity-50 pointer-events-none z-0" />
      <div className="absolute bottom-[-10%] right-[-10%] w-[45vw] h-[45vw] rounded-full bg-[#E7ECFF] blur-[120px] opacity-50 pointer-events-none z-0" />

      {/* Header bar */}
      <header className="relative z-10 mx-auto w-full max-w-7xl px-6 py-5 flex items-center justify-between shrink-0">
        <Link href="/" className="inline-flex items-baseline gap-0.5 text-xl font-extrabold tracking-[-0.05em] lowercase">
          <span>know</span>
          <span className="text-[#FF5A36]">tis</span>
        </Link>
        <div className="flex items-center gap-4">
          {currentSlide < TOTAL_SLIDES_DESKTOP - 1 && (
            <button 
              onClick={() => goToSlide(TOTAL_SLIDES_DESKTOP - 1)}
              className="text-xs font-bold text-[#686862] hover:text-[#171717] transition-colors"
            >
              Skip Onboarding
            </button>
          )}
          {isAuthenticated ? (
            <span className="text-xs font-extrabold px-4 py-2 rounded-full bg-[#171717] text-white border border-[#171717]">
              Redirecting
            </span>
          ) : (
            <Link href="/login" className="text-xs font-extrabold px-4 py-2 rounded-full border border-[#E9E9E6] bg-white hover:bg-[#F4F3EF] transition-all">
              Log in
            </Link>
          )}
        </div>
      </header>

      {/* Main Slide Window */}
      <div className="relative flex-1 z-10 w-full max-w-7xl mx-auto px-6 py-2 flex items-center justify-center overflow-hidden">
        <div className="w-full relative min-h-[580px] lg:min-h-[530px] flex items-center">
          <AnimatePresence initial={false} custom={direction} mode="wait">
            <motion.div
              key={currentSlide}
              custom={direction}
              variants={slideVariants}
              initial="enter"
              animate="center"
              exit="exit"
              className="w-full grid grid-cols-1 lg:grid-cols-12 gap-8 lg:gap-12 items-center"
            >
              
              {/* SLIDE 0: Welcome / Link Group Intro */}
              {currentSlide === 0 && (
                <>
                  <div className="lg:col-span-6 flex flex-col justify-center text-left">
                    <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-[#FFF0EB] text-[#FF5A36] text-[11px] font-black uppercase tracking-wider mb-6 w-fit">
                      <Sparkles className="w-3.5 h-3.5" />
                      Academic Signal
                    </div>
                    <h1 className="text-[38px] md:text-[50px] font-black leading-[1.05] tracking-[-0.04em] text-[#171717]">
                      Get the <span className="text-[#FF5A36]">academic signal</span>, mute the chat noise.
                    </h1>
                    <p className="mt-6 text-[15px] md:text-[17px] font-medium leading-relaxed text-[#686862] max-w-[54ch]">
                      University WhatsApp groups are flooded with hundreds of memes, jokes, and repeated questions. Knowtis runs silently in the background, extracting exam schedules, due dates, and lecture updates into a clean, calm dashboard.
                    </p>
                    <div className="mt-8 p-4 bg-white border border-[#E9E9E6] rounded-2xl flex items-start gap-3 shadow-sm max-w-md">
                      <Zap className="w-5 h-5 text-[#FF5A36] shrink-0 mt-0.5 fill-[#FF5A36]" />
                      <div className="text-xs text-[#686862] font-semibold leading-relaxed">
                        <span className="text-[#171717] font-bold block mb-0.5">Interactive Demo</span>
                        Click the &quot;Connect Group Chat&quot; button in the simulator to see how it extracts updates in real-time.
                      </div>
                    </div>
                  </div>

                  <div className="lg:col-span-6 flex justify-center">
                    <div className="relative w-full max-w-[360px] h-[460px] rounded-[38px] border-[6px] border-[#171717] bg-white shadow-[0_24px_48px_rgba(0,0,0,0.12)] overflow-hidden flex flex-col">
                      <div className="absolute top-0 inset-x-0 h-5 bg-white flex justify-center items-center z-40">
                        <div className="w-16 h-3 bg-[#171717] rounded-b-lg" />
                      </div>
                      
                      <div className="pt-6 px-4 pb-2 border-b border-[#F0F0ED] flex items-center justify-between bg-white shrink-0 z-30">
                        <span className="text-[10px] font-black uppercase tracking-wider text-[#686862] flex items-center gap-1">
                          <span className="w-1.5 h-1.5 rounded-full bg-[#FF5A36] animate-pulse" /> Live Simulator
                        </span>
                        <span className="text-[9px] font-bold text-[#FF5A36] bg-[#FFF0EB] px-2 py-0.5 rounded-full">Step 1 of 3</span>
                      </div>

                      <div className="flex-1 bg-[#FBFBFA] p-5 flex flex-col justify-between">
                        <div className="text-center pt-4">
                          <div className="mx-auto w-12 h-12 rounded-[18px] bg-[#FFF0EB] flex items-center justify-center mb-3">
                            <MessageCircle className="w-6 h-6 text-[#FF5A36]" />
                          </div>
                          <h3 className="text-base font-black tracking-[-0.03em]">Link your class chat</h3>
                          <p className="text-[11px] text-[#686862] font-semibold mt-1 px-4 leading-relaxed">
                            Copy the invite link of your university WhatsApp group and paste it here.
                          </p>
                        </div>

                        <div className="space-y-3">
                          <div className="space-y-1.5 text-left">
                            <label className="text-[9px] font-bold uppercase tracking-wider text-[#9A9A94] pl-1">Group Invite Link</label>
                            <div className="relative">
                              <input 
                                type="text" 
                                readOnly 
                                value="https://chat.whatsapp.com/invite/Kj9s8D7fPHY301" 
                                className="w-full text-[11px] font-semibold text-[#171717] bg-white border border-[#E9E9E6] rounded-xl py-2.5 px-3 outline-none pointer-events-none"
                              />
                              <div className="absolute right-2.5 top-2.5 flex items-center gap-1">
                                <span className="w-1 h-1 rounded-full bg-[#32B87B]" />
                                <span className="text-[8px] font-bold text-[#32B87B] uppercase">Valid</span>
                              </div>
                            </div>
                          </div>

                          <button
                            onClick={handleLinkSimulation}
                            disabled={isLinking}
                            className="w-full h-10 bg-[#171717] hover:bg-[#292929] text-white text-xs font-bold rounded-xl flex items-center justify-center gap-2 shadow-md transition-all active:scale-[0.98]"
                          >
                            {isLinking ? (
                              <>
                                <svg className="animate-spin h-3.5 w-3.5 text-white" fill="none" viewBox="0 0 24 24">
                                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                                </svg>
                                Connecting AI Listener...
                              </>
                            ) : (
                              <>
                                Connect Group Chat <ArrowRight className="w-3.5 h-3.5" />
                              </>
                            )}
                          </button>
                        </div>

                        <div className="flex items-center gap-2 p-2.5 bg-white border border-[#E9E9E6] rounded-xl">
                          <ShieldCheck className="w-4 h-4 text-[#32B87B] shrink-0" />
                          <span className="text-[9px] text-[#686862] leading-tight font-medium">
                            Knowtis only scans for academic details. Regular chats are instantly discarded in memory.
                          </span>
                        </div>
                      </div>
                      
                      <div className="h-3 bg-white flex justify-center items-center shrink-0">
                        <div className="w-20 h-1 bg-[#E9E9E6] rounded-full" />
                      </div>
                    </div>
                  </div>
                </>
              )}

              {/* SLIDE 1: Ingestion & Scan Animation */}
              {currentSlide === 1 && (
                <>
                  <div className="lg:col-span-6 flex flex-col justify-center text-left">
                    <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-[#E7ECFF] text-[#5F7CE2] text-[11px] font-black uppercase tracking-wider mb-6 w-fit">
                      <VolumeX className="w-3.5 h-3.5" />
                      Filter WhatsApp Noise
                    </div>
                    <h1 className="text-[38px] md:text-[50px] font-black leading-[1.05] tracking-[-0.04em] text-[#171717]">
                      Real-time message <span className="text-[#5F7CE2]">filtering</span>.
                    </h1>
                    <p className="mt-6 text-[15px] md:text-[17px] font-medium leading-relaxed text-[#686862] max-w-[54ch]">
                      As messages flood your university group chat, Knowtis runs in memory to separate actual lecture updates, exam cancellations, and assignments from casual conversations, memes, and redundant questions.
                    </p>
                    <div className="mt-8 flex flex-col gap-3 font-semibold text-xs text-[#686862]">
                      <div className="flex items-center gap-2">
                        <Check className="w-4 h-4 text-[#32B87B]" strokeWidth={3} />
                        <span>Mutes casual chat logs automatically</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <Check className="w-4 h-4 text-[#32B87B]" strokeWidth={3} />
                        <span>Isolates urgent notices in milliseconds</span>
                      </div>
                    </div>
                  </div>

                  <div className="lg:col-span-6 flex justify-center">
                    <div className="relative w-full max-w-[360px] h-[460px] rounded-[38px] border-[6px] border-[#171717] bg-white shadow-[0_24px_48px_rgba(0,0,0,0.12)] overflow-hidden flex flex-col">
                      <div className="absolute top-0 inset-x-0 h-5 bg-white flex justify-center items-center z-40">
                        <div className="w-16 h-3 bg-[#171717] rounded-b-lg" />
                      </div>
                      
                      <div className="pt-6 px-4 pb-2 border-b border-[#F0F0ED] flex items-center justify-between bg-white shrink-0 z-30">
                        <span className="text-[10px] font-black uppercase tracking-wider text-[#686862] flex items-center gap-1">
                          <span className="w-1.5 h-1.5 rounded-full bg-[#5F7CE2] animate-ping" /> AI Scanning
                        </span>
                        <span className="text-[9px] font-bold text-[#5F7CE2] bg-[#E7ECFF] px-2 py-0.5 rounded-full">Step 2 of 3</span>
                      </div>

                      <div className="flex-1 bg-[#E5DDD5] relative overflow-hidden flex flex-col justify-end p-3">
                        <div className="absolute inset-x-0 top-0 bg-[#075E54] text-white py-1.5 px-3 flex items-center gap-2 shadow-sm shrink-0 z-10">
                          <div className="w-6 h-6 rounded-full bg-white/20 flex items-center justify-center font-bold text-[10px] uppercase">
                            PH
                          </div>
                          <div>
                            <h4 className="text-[10px] font-black leading-tight">PHY 301 - Class Group</h4>
                            <p className="text-[8px] text-white/70">Tobi, Amara, Chinedu, Dr. Helen...</p>
                          </div>
                        </div>

                        <div className="flex-1 overflow-y-auto space-y-2 pt-8 pb-10">
                          {chatMessages.map(msg => (
                            <motion.div
                              key={msg.id}
                              initial={{ opacity: 0, y: 10, scale: 0.95 }}
                              animate={{ 
                                opacity: showScan && !msg.isSignal ? 0.25 : 1,
                                scale: 1,
                                filter: showScan && !msg.isSignal ? 'blur(0.5px)' : 'none'
                              }}
                              className={`max-w-[85%] rounded-xl p-2 text-[10px] shadow-[0_1px_1px_rgba(0,0,0,0.06)] relative ${
                                msg.role === 'lecturer' 
                                  ? 'bg-[#FFF0EB] border border-[#FF5A36]/30 mr-auto rounded-tl-none' 
                                  : 'bg-white ml-auto rounded-tr-none'
                              }`}
                            >
                              <span className={`block text-[8px] font-black mb-0.5 ${
                                msg.role === 'lecturer' ? 'text-[#FF5A36]' : 'text-blue-600'
                              }`}>
                                {msg.sender}
                              </span>
                              <p className="leading-snug font-medium text-[#2b2b2b]">{msg.text}</p>
                              
                              {showScan && msg.isSignal && (
                                <motion.div 
                                  className="absolute inset-0 rounded-xl border border-[#FF5A36] shadow-[0_0_8px_rgba(255,90,54,0.3)] pointer-events-none"
                                  initial={{ opacity: 0 }}
                                  animate={{ opacity: 1 }}
                                />
                              )}
                            </motion.div>
                          ))}
                        </div>

                        {showScan && !scanFinished && (
                          <motion.div
                            initial={{ top: '10%' }}
                            animate={{ top: '90%' }}
                            transition={{ duration: 2.5, ease: 'easeInOut' }}
                            className="absolute inset-x-0 h-0.5 bg-gradient-to-r from-transparent via-[#FF5A36] to-transparent shadow-[0_0_6px_#FF5A36] z-10 pointer-events-none"
                          />
                        )}

                        {showScan && (
                          <motion.div
                            initial={{ opacity: 0, y: 10 }}
                            animate={{ opacity: 1, y: 0 }}
                            className="absolute bottom-2 inset-x-3 bg-[#171717] text-white py-1.5 px-2.5 rounded-full flex items-center justify-between shadow-lg z-20"
                          >
                            <span className="text-[8px] font-black uppercase tracking-wider flex items-center gap-1">
                              <span className="w-1 h-1 rounded-full bg-[#FF5A36] animate-ping" />
                              {scanFinished ? 'Signal Extracted!' : 'Scanning Chat...'}
                            </span>
                            <span className="text-[8px] font-bold text-[#FF5A36]">Muted 83% Noise</span>
                          </motion.div>
                        )}
                      </div>
                      
                      <div className="h-3 bg-white flex justify-center items-center shrink-0">
                        <div className="w-20 h-1 bg-[#E9E9E6] rounded-full" />
                      </div>
                    </div>
                  </div>
                </>
              )}

              {/* SLIDE 2: Extracted Event Card */}
              {currentSlide === 2 && (
                <>
                  <div className="lg:col-span-6 flex flex-col justify-center text-left">
                    <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-[#EAF8F0] text-[#32B87B] text-[11px] font-black uppercase tracking-wider mb-6 w-fit">
                      <Check className="w-3.5 h-3.5" />
                      Structured Updates
                    </div>
                    <h1 className="text-[38px] md:text-[50px] font-black leading-[1.05] tracking-[-0.04em] text-[#171717]">
                      Structured <span className="text-[#32B87B]">academic timeline</span>.
                    </h1>
                    <p className="mt-6 text-[15px] md:text-[17px] font-medium leading-relaxed text-[#686862] max-w-[54ch]">
                      Extracted announcements are instantly structured into priority cards. You can sync due dates straight to your Google/Outlook calendar and view them in a consolidated dashboard.
                    </p>
                    <div className="mt-8 flex flex-col gap-3 font-semibold text-xs text-[#686862]">
                      <div className="flex items-center gap-2">
                        <Check className="w-4 h-4 text-[#32B87B]" strokeWidth={3} />
                        <span>Automatic Google & Outlook Calendar Sync</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <Check className="w-4 h-4 text-[#32B87B]" strokeWidth={3} />
                        <span>Interactive countdowns to important submissions</span>
                      </div>
                    </div>
                  </div>

                  <div className="lg:col-span-6 flex justify-center">
                    <div className="relative w-full max-w-[360px] h-[460px] rounded-[38px] border-[6px] border-[#171717] bg-white shadow-[0_24px_48px_rgba(0,0,0,0.12)] overflow-hidden flex flex-col">
                      <div className="absolute top-0 inset-x-0 h-5 bg-white flex justify-center items-center z-40">
                        <div className="w-16 h-3 bg-[#171717] rounded-b-lg" />
                      </div>
                      
                      <div className="pt-6 px-4 pb-2 border-b border-[#F0F0ED] flex items-center justify-between bg-white shrink-0 z-30">
                        <span className="text-[10px] font-black uppercase tracking-wider text-[#686862] flex items-center gap-1">
                          <Check className="w-3.5 h-3.5 text-[#32B87B]" /> Extracted Update
                        </span>
                        <span className="text-[9px] font-bold text-[#32B87B] bg-[#EAF8F0] px-2 py-0.5 rounded-full">Step 3 of 3</span>
                      </div>

                      <div className="flex-1 bg-[#F4F3EF] p-5 flex flex-col justify-between overflow-hidden">
                        <div className="space-y-4 pt-2">
                          <div className="text-center">
                            <span className="inline-block text-[8px] font-black uppercase tracking-wider bg-emerald-100 text-emerald-700 px-2 py-0.5 rounded-full mb-1">
                              Successfully Added
                            </span>
                            <h4 className="text-xs font-black text-[#686862]">Structured Dashboard Update</h4>
                          </div>

                          <motion.div
                            initial={{ scale: 0.9, opacity: 0 }}
                            animate={{ scale: 1, opacity: 1 }}
                            className="bg-[#FFB3A7] border border-[#1E1B2E] rounded-[20px] p-4 shadow-sm relative transform -rotate-1"
                          >
                            <div className="absolute top-2 right-2.5 w-4 h-4 rounded-full bg-white/40 border border-[#1E1B2E] flex items-center justify-center">
                              <Clock className="w-2.5 h-2.5 text-[#1E1B2E]" />
                            </div>
                            
                            <span className="inline-block text-[8px] font-black uppercase tracking-wider bg-white/60 text-[#1E1B2E] px-1.5 py-0.5 rounded-md border border-[#1E1B2E] mb-2">
                              PHY 301 · URGENT
                            </span>
                            
                            <h5 className="text-[13px] font-black leading-tight text-[#1E1B2E] tracking-tight">
                              Physics 301 Lab Quiz & Lab Report 2
                            </h5>
                            
                            <div className="mt-3 space-y-1.5 border-t border-[#1E1B2E]/10 pt-2 text-[10px] font-bold text-[#1E1B2E]/80">
                              <div className="flex items-center gap-1.5">
                                <CalendarDays className="w-3.5 h-3.5" />
                                <span>Thursday @ 2:00 PM</span>
                              </div>
                              <div className="flex items-center gap-1.5">
                                <Info className="w-3.5 h-3.5" />
                                <span>Lab Hall C (Report due 4:00 PM)</span>
                              </div>
                            </div>
                          </motion.div>

                          <motion.div
                            initial={{ opacity: 0, x: -10 }}
                            animate={{ opacity: 1, x: 0 }}
                            className="bg-white border border-[#E9E9E6] rounded-xl p-2.5 flex items-start gap-2 shadow-[0_4px_12px_rgba(0,0,0,0.02)]"
                          >
                            <div className="w-6 h-6 rounded-full bg-[#25D366] flex items-center justify-center shrink-0">
                              <MessageCircle className="w-3.5 h-3.5 text-white fill-white" />
                            </div>
                            <div className="text-left min-w-0 flex-1">
                              <p className="text-[9px] font-black text-[#171717] flex justify-between items-center w-full">
                                <span>Knowtis Alert</span>
                                <span className="text-[8px] text-[#9A9A94] font-normal">Just now</span>
                              </p>
                              <p className="text-[9px] text-[#686862] font-semibold mt-0.5 leading-snug truncate">
                                PHY 301: Lab Quiz is Thursday 2:00 PM in Lab Hall C. Added.
                              </p>
                            </div>
                          </motion.div>
                        </div>

                        <button
                          onClick={resetSimulation}
                          className="w-full h-8 border border-[#E9E9E6] bg-white hover:bg-[#FBFBFA] text-[#686862] hover:text-[#171717] text-[10px] font-bold rounded-lg flex items-center justify-center gap-1 transition-all"
                        >
                          <RotateCcw className="w-3 h-3" /> Run Simulation Again
                        </button>
                      </div>
                      
                      <div className="h-3 bg-white flex justify-center items-center shrink-0">
                        <div className="w-20 h-1 bg-[#E9E9E6] rounded-full" />
                      </div>
                    </div>
                  </div>
                </>
              )}

              {/* SLIDE 3: Bento Grid Features */}
              {currentSlide === 3 && (
                <div className="lg:col-span-12 w-full text-center flex flex-col justify-center">
                  <div className="max-w-xl mx-auto mb-8">
                    <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-[#FFF5E1] text-[#F2A53C] text-[11px] font-black uppercase tracking-wider mb-3">
                      <Zap className="w-3.5 h-3.5 fill-[#F2A53C]" />
                      Features Overview
                    </div>
                    <h2 className="text-3xl md:text-4xl font-black tracking-[-0.04em]">
                      Built with smart academic tools
                    </h2>
                    <p className="mt-2 text-xs md:text-sm text-[#686862] font-semibold leading-relaxed">
                      Everything a student needs to stay informed and completely organized, without downloading another social media client.
                    </p>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-4 gap-4 max-w-5xl mx-auto w-full">
                    
                    {/* Timetable OCR */}
                    <div className="bg-white border border-[#E9E9E6] rounded-[24px] p-5 text-left shadow-sm flex flex-col justify-between min-h-[160px]">
                      <div>
                        <div className="w-8 h-8 rounded-[10px] bg-[#E7ECFF] flex items-center justify-center mb-3">
                          <ImageIcon className="w-4 h-4 text-[#5F7CE2]" />
                        </div>
                        <h3 className="text-sm font-black tracking-tight">Timetable OCR</h3>
                        <p className="mt-1 text-[11px] text-[#686862] leading-relaxed font-semibold">
                          Forward screenshot flyers with <span className="text-[#FF5A36]">@Knowtis extract</span> on WhatsApp to auto-extract schedules.
                        </p>
                      </div>
                    </div>

                    {/* Night Brief */}
                    <div className="bg-white border border-[#E9E9E6] rounded-[24px] p-5 text-left shadow-sm flex flex-col justify-between min-h-[160px]">
                      <div>
                        <div className="w-8 h-8 rounded-[10px] bg-[#FFF5E1] flex items-center justify-center mb-3">
                          <Bell className="w-4 h-4 text-[#F2A53C]" />
                        </div>
                        <h3 className="text-sm font-black tracking-tight">The Night Brief</h3>
                        <p className="mt-1 text-[11px] text-[#686862] leading-relaxed font-semibold">
                          Get one clean brief delivered directly to your phone every evening at 8:00 PM with tomorrow&apos;s schedule.
                        </p>
                      </div>
                    </div>

                    {/* Semantic Deduplication */}
                    <div className="bg-white border border-[#E9E9E6] rounded-[24px] p-5 text-left shadow-sm flex flex-col justify-between min-h-[160px]">
                      <div>
                        <div className="w-8 h-8 rounded-[10px] bg-[#EAF8F0] flex items-center justify-center mb-3">
                          <VolumeX className="w-4 h-4 text-[#32B87B]" />
                        </div>
                        <h3 className="text-sm font-black tracking-tight">Deduplication</h3>
                        <p className="mt-1 text-[11px] text-[#686862] leading-relaxed font-semibold">
                          Mutes duplicate forwards and merges repeated announcements into a single structured calendar update.
                        </p>
                      </div>
                    </div>

                    {/* Calendar Sync */}
                    <div className="bg-white border border-[#E9E9E6] rounded-[24px] p-5 text-left shadow-sm flex flex-col justify-between min-h-[160px]">
                      <div>
                        <div className="w-8 h-8 rounded-[10px] bg-[#FFF0EB] flex items-center justify-center mb-3">
                          <CalendarDays className="w-4 h-4 text-[#FF5A36]" />
                        </div>
                        <h3 className="text-sm font-black tracking-tight">Calendar Sync</h3>
                        <p className="mt-1 text-[11px] text-[#686862] leading-relaxed font-semibold">
                          Instantly pushes all extracted updates directly into your Google Calendar or Outlook in one click.
                        </p>
                      </div>
                    </div>

                  </div>
                </div>
              )}

              {/* SLIDE 4: Security & Privacy */}
              {currentSlide === 4 && (
                <div className="lg:col-span-12 w-full text-center flex flex-col justify-center">
                  <div className="max-w-xl mx-auto mb-8 flex flex-col items-center">
                    <div className="w-12 h-12 rounded-full bg-[#EAF8F0] flex items-center justify-center mb-4">
                      <ShieldCheck className="w-6 h-6 text-[#32B87B]" />
                    </div>
                    <h2 className="text-3xl md:text-4xl font-black tracking-[-0.04em]">
                      Built with strict student privacy
                    </h2>
                    <p className="mt-2 text-xs md:text-sm text-[#686862] font-semibold leading-relaxed">
                      Knowtis runs local classification algorithms to identify course codes and assignment key phrases. We ignore all non-academic chats, media files, and private user details.
                    </p>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-4xl mx-auto w-full text-left">
                    <div className="p-5 rounded-2xl bg-white border border-[#E9E9E6] shadow-sm">
                      <div className="w-1.5 h-1.5 bg-[#32B87B] rounded-full mb-2" />
                      <h4 className="text-xs font-black uppercase text-[#171717]">No Personal DMs</h4>
                      <p className="text-[11px] text-[#686862] font-semibold mt-1 leading-relaxed">
                        We never read or scan your private WhatsApp messages, and only index group chats you explicitly authorize.
                      </p>
                    </div>

                    <div className="p-5 rounded-2xl bg-white border border-[#E9E9E6] shadow-sm">
                      <div className="w-1.5 h-1.5 bg-[#32B87B] rounded-full mb-2" />
                      <h4 className="text-xs font-black uppercase text-[#171717]">100% Data Encryption</h4>
                      <p className="text-[11px] text-[#686862] font-semibold mt-1 leading-relaxed">
                        All extracted academic events are stored using industry-standard AES-256 databases and encrypted in transit.
                      </p>
                    </div>

                    <div className="p-5 rounded-2xl bg-white border border-[#E9E9E6] shadow-sm">
                      <div className="w-1.5 h-1.5 bg-[#32B87B] rounded-full mb-2" />
                      <h4 className="text-xs font-black uppercase text-[#171717]">Full User Ownership</h4>
                      <p className="text-[11px] text-[#686862] font-semibold mt-1 leading-relaxed">
                        You hold full control. Unlink any class group or permanently wipe your data on demand in one click.
                      </p>
                    </div>
                  </div>
                </div>
              )}

              {/* SLIDE 5: CTA / Final Screen */}
              {currentSlide === 5 && (
                <div className="lg:col-span-12 w-full text-center flex flex-col justify-center py-6">
                  <div className="max-w-xl mx-auto mb-8">
                    <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-[#FFF0EB] text-[#FF5A36] text-[11px] font-black uppercase tracking-wider mb-3">
                      <Zap className="w-3.5 h-3.5 fill-[#FF5A36]" />
                      Get Started
                    </div>
                    <h2 className="text-4xl md:text-5xl font-black tracking-[-0.04em] leading-tight">
                      Stop scrolling. Start tracking.
                    </h2>
                    <p className="mt-3 text-xs md:text-sm text-[#686862] font-semibold leading-relaxed">
                      Link your first class WhatsApp group chat in under two minutes and let Knowtis organize your academic schedule.
                    </p>
                  </div>

                  <div className="flex flex-col sm:flex-row gap-3 justify-center max-w-md mx-auto w-full px-4">
                    <a 
                      href={GOOGLE_OAUTH_URL} 
                      className="flex h-[52px] items-center justify-center gap-2.5 rounded-full border border-[#E9E9E6] bg-white text-[14px] font-bold text-[#171717] shadow-sm hover:bg-[#FBFBFA] transition-all active:scale-[0.98] px-6 w-full"
                    >
                      <GoogleIcon />
                      Continue with Google
                    </a>
                    <Link 
                      href="/register" 
                      className="flex h-[52px] items-center justify-center gap-2 rounded-full bg-[#171717] text-[14px] font-bold text-white shadow-[0_12px_24px_rgba(30,30,30,0.15)] hover:bg-[#2e2e2e] transition-all active:scale-[0.98] px-6 w-full"
                    >
                      Sign Up with Email <ArrowRight className="w-4 h-4" />
                    </Link>
                  </div>

                  <p className="mt-6 text-[11px] text-[#9A9A94] font-bold uppercase tracking-wider">
                    Already have an account?{' '}
                    <Link href="/login" className="text-[#FF5A36] hover:underline">Log in here</Link>
                  </p>
                </div>
              )}

            </motion.div>
          </AnimatePresence>
        </div>
      </div>

      {/* Slide Navigation Controls */}
      <footer className="relative z-10 mx-auto w-full max-w-7xl px-6 py-6 flex items-center justify-between shrink-0">
        {/* Left Side: Back Button */}
        <div className="w-[100px] text-left">
          {currentSlide > 0 && (
            <button
              onClick={handleBack}
              className="inline-flex items-center gap-1.5 text-xs font-extrabold text-[#686862] hover:text-[#171717] transition-colors py-2 px-3 rounded-full hover:bg-white/80 border border-transparent hover:border-[#E9E9E6]"
            >
              <ChevronLeft className="w-4 h-4" /> Back
            </button>
          )}
        </div>

        {/* Center: Progress Indicators */}
        <div className="flex items-center gap-2">
          {Array.from({ length: TOTAL_SLIDES_DESKTOP }).map((_, i) => (
            <button
              key={i}
              onClick={() => goToSlide(i)}
              className={`h-1.5 rounded-full transition-all duration-300 ${
                currentSlide === i ? 'w-6 bg-[#171717]' : 'w-1.5 bg-[#171717]/15 hover:bg-[#171717]/30'
              }`}
              aria-label={`Go to slide ${i + 1}`}
            />
          ))}
        </div>

        {/* Right Side: Next Button */}
        <div className="w-[100px] text-right">
          {currentSlide < TOTAL_SLIDES_DESKTOP - 1 ? (
            <button
              onClick={handleNext}
              className="inline-flex items-center gap-1.5 text-xs font-extrabold text-[#171717] bg-white border border-[#E9E9E6] hover:bg-[#F4F3EF] transition-all py-2 px-4 rounded-full shadow-sm active:scale-[0.98]"
            >
              Next <ChevronRight className="w-4 h-4" />
            </button>
          ) : (
            <div className="w-4 h-4 invisible" />
          )}
        </div>
      </footer>
    </main>
  );
}

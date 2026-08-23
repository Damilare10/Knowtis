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
  Lock, 
  ArrowLeft
} from 'lucide-react';
import { GOOGLE_OAUTH_URL } from '@/lib/api';

import { RollerSpinner, GoogleIcon, AppleIcon } from '@/components/ui/icons';

const TOTAL_SLIDES = 5;

export default function OnboardingPage() {
  const router = useRouter();
  const [mounted, setMounted] = useState(false);
  const [currentSlide, setCurrentSlide] = useState(0);
  const [navTarget, setNavTarget] = useState<string | null>(null);
  
  // Interactive notification chips for Screen 4
  const [filterChips, setFilterChips] = useState({
    assignments: true,
    exams: true,
    events: false,
    urgentOnly: true,
  });

  // Hydration safety check to prevent DOM removeChild crashes
  useEffect(() => {
    setMounted(true);
  }, []);

  const goToSlide = useCallback((targetSlide: number) => {
    if (targetSlide < 0 || targetSlide >= TOTAL_SLIDES) return;
    setCurrentSlide(targetSlide);
  }, []);

  const handleNext = useCallback(() => {
    if (currentSlide < TOTAL_SLIDES - 1) {
      goToSlide(currentSlide + 1);
    }
  }, [currentSlide, goToSlide]);

  const handleBack = useCallback(() => {
    if (currentSlide > 0) {
      goToSlide(currentSlide - 1);
    }
  }, [currentSlide, goToSlide]);

  const finishOnboarding = useCallback((targetPath: string = '/dashboard') => {
    setNavTarget(targetPath);
    try {
      window.localStorage.setItem('knowtis_onboarded', 'true');
    } catch {
      // Safe catch
    }
    router.push(targetPath);
  }, [router]);

  // Keyboard navigation
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'ArrowRight') handleNext();
      if (e.key === 'ArrowLeft') handleBack();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleNext, handleBack]);

  if (!mounted) {
    return <main className="min-h-[100dvh] bg-[#FBFBFA]" />;
  }

  // Background Gradient Theme per Screen
  const bgGradients = [
    'from-[#EAF7F3] via-[#F4FAFA] to-[#FBFBFA]', // Mint (Screen 1)
    'from-[#FFF0EC] via-[#FFF8F6] to-[#FBFBFA]', // Peach/Coral (Screen 2)
    'from-[#E8F1FC] via-[#F3F7FD] to-[#FBFBFA]', // Sky Blue (Screen 3)
    'from-[#FFFCE6] via-[#FFFEFA] to-[#FBFBFA]', // Light Yellow (Screen 4)
    'from-[#EFEFFE] via-[#F9F9FF] to-[#FBFBFA]'  // Light Lavender (Screen 5)
  ];

  return (
    <main
      suppressHydrationWarning
      className={`relative min-h-[100dvh] flex flex-col justify-between items-center overflow-x-hidden overflow-y-auto bg-gradient-to-b ${bgGradients[currentSlide]} text-[#171717] font-sans px-6 transition-all duration-300 ease-out select-none`}
      style={{
        paddingTop: 'max(16px, env(safe-area-inset-top, 16px))',
        paddingBottom: 'max(16px, env(safe-area-inset-bottom, 16px))',
      }}
    >
      {/* Top Header (Skip Button top right) */}
      <header className="w-full max-w-[420px] flex justify-end shrink-0 py-1 z-20">
        {currentSlide < TOTAL_SLIDES - 1 && (
          <button 
            type="button"
            onClick={() => goToSlide(TOTAL_SLIDES - 1)}
            className="text-xs font-black uppercase tracking-wider text-[#A3A29C] hover:text-[#171717] transition-colors py-1 px-2"
          >
            Skip
          </button>
        )}
      </header>

      {/* Main Slide Workspace */}
      <div className="flex-1 w-full max-w-[420px] flex flex-col items-center justify-center py-2 my-auto z-10 relative">
        <div className="w-full flex flex-col items-center text-center">
          
          {/* --- HERO SECTION CONTAINER with transitions --- */}
          <AnimatePresence mode="wait">
            <motion.div
              key={currentSlide}
              initial={{ opacity: 0, x: 30, filter: 'blur(4px)' }}
              animate={{ opacity: 1, x: 0, filter: 'blur(0px)' }}
              exit={{ opacity: 0, x: -30, filter: 'blur(4px)' }}
              transition={{ 
                x: { type: 'spring', stiffness: 300, damping: 30 }, 
                opacity: { duration: 0.3 },
                filter: { duration: 0.3 }
              }}
              className="mb-4 sm:mb-6 flex justify-center w-full relative"
            >
            
            {/* HERO SCREEN 1: Chaotic Noise */}
            {currentSlide === 0 && (
              <div className="relative w-[min(280px,68vw)] h-[min(280px,30vh)] max-h-[300px] rounded-[2.5rem] sm:rounded-[2.8rem] bg-white/95 border border-[#E9E9E6] shadow-[0_20px_48px_rgba(0,0,0,0.06)] flex items-center justify-center overflow-visible">
                
                {/* Central WhatsApp Icon Ring */}
                <div className="w-20 h-20 rounded-full bg-[#EAF8F0] border-2 border-[#32B87B] flex items-center justify-center text-[#32B87B] shadow-sm relative z-10">
                  <MessageCircle className="w-10 h-10 fill-[#32B87B]/10" />
                </div>
                
                {/* Static Noise Badges */}
                <span className="absolute top-6 left-3 bg-white border border-[#E9E9E6] text-[11px] font-extrabold text-[#74736D] px-3 py-1 rounded-full shadow-xs z-20">
                  Meme 🐸
                </span>

                <span className="absolute top-12 right-4 bg-white border border-[#E9E9E6] text-[11px] font-extrabold text-[#74736D] px-3 py-1 rounded-full shadow-xs z-20">
                  LOL 😂
                </span>

                <span className="absolute bottom-20 -right-2 bg-white border border-[#E9E9E6] text-[11px] font-extrabold text-[#74736D] px-3 py-1 rounded-full shadow-xs z-20">
                  Who has notes?
                </span>

                <span className="absolute bottom-16 -left-3 bg-white border border-[#E9E9E6] text-[11px] font-extrabold text-[#74736D] px-3 py-1 rounded-full shadow-xs z-20">
                  Same?
                </span>

                <span className="absolute top-3 left-1/3 bg-white border border-[#E9E9E6] text-[10px] font-extrabold text-[#74736D] px-2.5 py-0.5 rounded-full shadow-xs z-20">
                  Good morning 🌞
                </span>

                <span className="absolute bottom-6 right-8 bg-white border border-[#E9E9E6] text-[10px] font-bold text-[#74736D] px-2.5 py-0.5 rounded-full shadow-xs z-20">
                  Football discussion ⚽
                </span>

                <span className="absolute -bottom-3 left-1/4 bg-[#FFF0EB] border border-[#FF5A36]/40 text-[11px] font-black text-[#FF5A36] px-3.5 py-1 rounded-full shadow-md z-30 flex items-center gap-1">
                  Deadline? 🚨
                </span>
                
                {/* Warning Badge Top Right */}
                <div className="absolute -top-3 -right-3 w-10 h-10 rounded-full bg-[#FF5A36] flex items-center justify-center text-white font-black text-xl shadow-[0_8px_20px_rgba(255,90,54,0.35)] border-2 border-white z-30">
                  !
                </div>
              </div>
            )}

            {/* HERO SCREEN 2: AI Filters Clutter */}
            {currentSlide === 1 && (
              <div className="relative w-[min(280px,68vw)] h-[min(280px,30vh)] max-h-[300px] rounded-[2.5rem] sm:rounded-[2.8rem] bg-white/95 border border-[#E9E9E6] shadow-[0_20px_48px_rgba(0,0,0,0.06)] flex flex-col justify-center p-5 overflow-hidden">
                
                {/* Blurred Messy Chat Lines */}
                <div className="space-y-2 opacity-40 blur-[0.6px] transition-all mb-2">
                  <div className="bg-[#E9E9E6] rounded-xl p-2 text-[9px] font-bold text-[#74736D] w-4/5 ml-auto">
                    Lol did u guys do the physics homework yet?
                  </div>
                  <div className="bg-[#E9E9E6] rounded-xl p-2 text-[9px] font-bold text-[#74736D] w-3/5 ml-auto">
                    Nah, too busy playing FIFA 😂
                  </div>
                </div>

                {/* Target Extracted Signal Card */}
                <div className="my-2 bg-[#EAF8F0] border-2 border-[#32B87B] rounded-2xl p-3.5 shadow-sm text-left relative z-20">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-[8px] font-black text-[#32B87B] uppercase tracking-wider">PHY 301 · LECTURER ALERT</span>
                    <div className="w-4 h-4 rounded-full bg-[#32B87B] flex items-center justify-center text-white">
                      <Check className="w-2.5 h-2.5" strokeWidth={3} />
                    </div>
                  </div>
                  <p className="text-[10px] font-black leading-snug text-slate-800">
                    Lab report extension until Thursday 4pm. Lab quiz is Thursday 2pm.
                  </p>
                </div>

                {/* Static Highlight Laser Bar */}
                <div className="w-full h-0.5 bg-gradient-to-r from-transparent via-[#32B87B] to-transparent shadow-[0_0_8px_#32B87B] my-2" />

                <div className="flex justify-center items-center gap-1.5 text-[9px] font-black text-[#32B87B] mt-1">
                  <Sparkles className="w-3 h-3" />
                  <span>AI Signal Isolated</span>
                </div>
              </div>
            )}

            {/* HERO SCREEN 3: Connect Class Chat */}
            {currentSlide === 2 && (
              <div className="relative w-[min(280px,68vw)] h-[min(280px,30vh)] max-h-[300px] rounded-[2.5rem] sm:rounded-[2.8rem] bg-white/95 border border-[#E9E9E6] shadow-[0_20px_48px_rgba(0,0,0,0.06)] flex flex-col justify-between p-6 overflow-visible">
                
                {/* Simulated Invite Link Box */}
                <div className="space-y-1.5 text-left">
                  <span className="text-[8.5px] font-black text-[#9A9A94] uppercase tracking-wider pl-1 block">Link Class WhatsApp</span>
                  <div className="bg-white border border-[#E9E9E6] rounded-xl py-2.5 px-3 flex items-center justify-between shadow-xs">
                    <span className="text-[10px] font-bold text-slate-400 truncate w-40">chat.whatsapp.com/invite/Kj9s...</span>
                    <span className="w-2.5 h-2.5 rounded-full bg-[#32B87B]" />
                  </div>
                </div>

                {/* Read-Only Shield Card */}
                <div className="flex items-center gap-3 bg-white border border-slate-100 p-3.5 rounded-2xl shadow-sm">
                  <div className="w-10 h-10 rounded-xl bg-blue-50 flex items-center justify-center text-[#4285F4] shrink-0">
                    <Lock className="w-5 h-5" />
                  </div>
                  <div className="text-left min-w-0">
                    <span className="block text-[10px] font-black text-slate-800">Read-Only Safe Listener</span>
                    <span className="block text-[8.5px] font-bold text-slate-400 leading-tight">No DMs or private data accessed.</span>
                  </div>
                </div>

              </div>
            )}

            {/* HERO SCREEN 4: Smart Notifications */}
            {currentSlide === 3 && (
              <div className="relative w-[min(280px,68vw)] h-[min(280px,30vh)] max-h-[300px] rounded-[2.5rem] sm:rounded-[2.8rem] bg-white/95 border border-[#E9E9E6] shadow-[0_20px_48px_rgba(0,0,0,0.06)] flex flex-col items-center justify-center p-5 overflow-visible">
                
                {/* Still Bell Icon */}
                <div className="w-16 h-16 rounded-full bg-[#FFF5E1] border-2 border-[#F2A53C] flex items-center justify-center text-[#F2A53C] shadow-sm mb-2">
                  <Bell className="w-8 h-8 fill-[#F2A53C]/10" />
                </div>

                {/* Interactive Filter Chips Row */}
                <div className="flex gap-1.5 my-2">
                  <button 
                    type="button"
                    onClick={() => setFilterChips(p => ({ ...p, assignments: !p.assignments }))}
                    className={`px-2.5 py-0.5 rounded-full text-[9px] font-black ${
                      filterChips.assignments ? 'bg-[#FF5A36] text-white' : 'bg-white text-slate-400 border border-slate-200'
                    }`}
                  >
                    Assignments {filterChips.assignments ? '✓' : ''}
                  </button>
                  <button 
                    type="button"
                    onClick={() => setFilterChips(p => ({ ...p, urgentOnly: !p.urgentOnly }))}
                    className={`px-2.5 py-0.5 rounded-full text-[9px] font-black ${
                      filterChips.urgentOnly ? 'bg-[#F2A53C] text-white' : 'bg-white text-slate-400 border border-slate-200'
                    }`}
                  >
                    Urgent Only {filterChips.urgentOnly ? '✓' : ''}
                  </button>
                </div>

                {/* Static Notification Pills */}
                <span className="absolute top-8 left-4 bg-white border border-[#FFF0EB] text-[10px] font-black text-[#FF5A36] px-3 py-1 rounded-full shadow-xs">
                  Urgent 🚨
                </span>

                <span className="absolute bottom-8 right-4 bg-white border border-[#E9E9E6] text-[10px] font-bold text-[#74736D] px-3 py-1 rounded-full shadow-xs">
                  Night Brief 🌙
                </span>
              </div>
            )}

            {/* HERO SCREEN 5: Auto-Sync */}
            {currentSlide === 4 && (
              <div className="relative w-[min(280px,68vw)] h-[min(280px,30vh)] max-h-[300px] rounded-[2.5rem] sm:rounded-[2.8rem] bg-white/95 border border-[#E9E9E6] shadow-[0_20px_48px_rgba(0,0,0,0.06)] flex flex-col justify-between p-6 overflow-visible">
                
                {/* Calendar Snippet */}
                <div className="bg-white border border-[#E9E9E6] rounded-2xl p-3 shadow-xs space-y-2">
                  <div className="flex items-center justify-between border-b border-slate-100 pb-1.5">
                    <span className="text-[10px] font-black text-slate-800">Thursday 16</span>
                    <div className="w-2 h-2 rounded-full bg-[#FF5A36]" />
                  </div>
                  <div className="bg-[#FFF0EB] border border-[#FFD8CD] rounded-xl p-2 text-left">
                    <span className="block text-[8.5px] font-black text-[#FF5A36] uppercase tracking-wider">PHY 301 · 2:00 PM</span>
                    <span className="block text-[10px] font-black text-slate-800 leading-tight">Physics Lab Quiz</span>
                  </div>
                </div>

                {/* Google & Apple Pills */}
                <div className="flex gap-2 justify-center">
                  <span className="bg-white border border-[#E9E9E6] px-4 py-1.5 rounded-full text-[10px] font-bold text-slate-700 flex items-center gap-1.5 shadow-xs">
                    <GoogleIcon /> Google
                  </span>
                  <span className="bg-white border border-[#E9E9E6] px-4 py-1.5 rounded-full text-[10px] font-bold text-slate-700 flex items-center gap-1.5 shadow-xs">
                    <AppleIcon /> Apple
                  </span>
                </div>

            </div>
          )}

          </motion.div>
        </AnimatePresence>

        {/* --- PROGRESS INDICATOR (Directly below Hero Box) --- */}
          <div className="mb-5 flex justify-center items-center gap-1.5">
            {Array.from({ length: TOTAL_SLIDES }).map((_, i) => (
              <button
                key={i}
                type="button"
                onClick={() => goToSlide(i)}
                className={`h-1.5 rounded-full transition-all duration-300 ${
                  currentSlide === i ? 'w-7 bg-[#171717]' : 'w-1.5 bg-[#171717]/20 hover:bg-[#171717]/40'
                }`}
                aria-label={`Go to slide ${i + 1}`}
              />
            ))}
          </div>

          {/* --- HEADLINE & BODY COPY AREA --- */}
          <AnimatePresence mode="wait">
            <motion.div
              key={currentSlide}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              transition={{ duration: 0.3, delay: 0.1 }}
              className="w-full max-w-[360px] px-2"
            >
            
            {currentSlide === 0 && (
              <>
                <h2 className="text-[28px] sm:text-[32px] font-black tracking-tight leading-[1.1] text-[#171717]">
                  University chats are <span className="bg-[#FF5A36] text-white px-2.5 py-0.5 rounded-xl inline-block transform -rotate-1 shadow-xs">chaotic noise</span> .
                </h2>
                <p className="mt-3 text-[14px] font-semibold leading-relaxed text-[#686862]">
                  Crucial academic announcements from lecturers get buried within minutes under hundreds of student memes, jokes, and repeated questions.
                </p>
              </>
            )}

            {currentSlide === 1 && (
              <>
                <h2 className="text-[28px] sm:text-[32px] font-black tracking-tight leading-[1.1] text-[#171717]">
                  Knowtis filters out <span className="bg-[#32B87B] text-white px-2.5 py-0.5 rounded-xl inline-block transform -rotate-1 shadow-xs">the clutter</span> .
                </h2>
                <p className="mt-3 text-[14px] font-semibold leading-relaxed text-[#686862]">
                  Our silent AI listener monitors your group chat in real-time, automatically isolating due dates, assignment specs, and timetable changes.
                </p>
              </>
            )}

            {currentSlide === 2 && (
              <>
                <h2 className="text-[28px] sm:text-[32px] font-black tracking-tight leading-[1.1] text-[#171717]">
                  Connect your class chat <span className="bg-[#4285F4] text-white px-2.5 py-0.5 rounded-xl inline-block transform -rotate-1 shadow-xs">in seconds</span> .
                </h2>
                <p className="mt-3 text-[14px] font-semibold leading-relaxed text-[#686862]">
                  Just paste your group invite link. Knowtis joins silently as an offline read-only watcher—no DMs, no phone numbers shared, no spam.
                </p>
              </>
            )}

            {currentSlide === 3 && (
              <>
                <h2 className="text-[28px] sm:text-[32px] font-black tracking-tight leading-[1.1] text-[#171717]">
                  Get notified on <span className="bg-[#F2A53C] text-white px-2.5 py-0.5 rounded-xl inline-block transform -rotate-1 shadow-xs">your terms</span> .
                </h2>
                <p className="mt-3 text-[14px] font-semibold leading-relaxed text-[#686862]">
                  Receive priority WhatsApp alerts only when deadlines change, plus a consolidated &quot;Night Brief&quot; summary every evening.
                </p>
              </>
            )}

            {currentSlide === 4 && (
              <>
                <h2 className="text-[28px] sm:text-[32px] font-black tracking-tight leading-[1.1] text-[#171717]">
                  Your schedule, <span className="bg-[#FF5A36] text-white px-2.5 py-0.5 rounded-xl inline-block transform -rotate-1 shadow-xs">auto-synced</span> .
                </h2>
                <p className="mt-3 text-[14px] font-semibold leading-relaxed text-[#686862]">
                  Every extracted deadline is instantly pushed to your calendar. No more copying dates manually, no more saving screenshots.
                </p>
              </>
            )}

          </motion.div>
        </AnimatePresence>

        </div>
      </div>

      {/* --- BOTTOM ACTION BUTTONS AREA --- */}
      <footer className="w-full max-w-[340px] flex flex-col gap-2.5 shrink-0 mt-auto pb-4 pt-2 z-20">
        
        {currentSlide < TOTAL_SLIDES - 1 ? (
          <div className="flex items-center gap-3 w-full">
            {/* Back button */}
            {currentSlide > 0 && (
              <button
                type="button"
                onClick={handleBack}
                className="w-12 h-12 rounded-full bg-white border border-[#E9E9E6] shadow-xs flex items-center justify-center text-[#171717] active:scale-95 transition-all shrink-0"
                aria-label="Back"
              >
                <ArrowLeft className="w-5 h-5" />
              </button>
            )}
            {/* Primary Continue Button */}
            <button
              type="button"
              onClick={handleNext}
              className="flex-1 h-[54px] bg-[#171717] hover:bg-[#2c2c2c] text-white font-bold rounded-full flex items-center justify-center gap-2 text-sm shadow-[0_8px_20px_rgba(0,0,0,0.12)] active:scale-[0.98] transition-all group"
            >
              <span>Continue</span>
              <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
            </button>
          </div>
        ) : (
          /* Slide 4 (Final Screen: Auto-sync) Action Stack with Roller Spinners */
          <div className="flex flex-col gap-2.5 w-full">
            <button
              type="button"
              disabled={navTarget !== null}
              onClick={() => finishOnboarding('/register')}
              className="w-full h-[54px] bg-[#171717] hover:bg-[#2c2c2c] text-white font-bold rounded-full flex items-center justify-center gap-2 text-sm shadow-[0_8px_20px_rgba(0,0,0,0.12)] active:scale-[0.98] transition-all group disabled:opacity-80"
            >
              {navTarget === '/register' ? (
                <>
                  <RollerSpinner className="w-4 h-4 text-white" />
                  <span>Loading...</span>
                </>
              ) : (
                <>
                  <span>Sign Up</span>
                  <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
                </>
              )}
            </button>

            <button
              type="button"
              disabled={navTarget !== null}
              onClick={() => finishOnboarding('/login')}
              className="w-full h-[54px] bg-white border border-[#E9E9E6] hover:bg-[#FBFBFA] text-[#171717] font-bold rounded-full flex items-center justify-center gap-2 text-sm shadow-xs active:scale-[0.98] transition-all disabled:opacity-80"
            >
              {navTarget === '/login' ? (
                <>
                  <RollerSpinner className="w-4 h-4 text-[#171717]" />
                  <span>Loading...</span>
                </>
              ) : (
                <span>Log In</span>
              )}
            </button>

            <div className="flex items-center gap-3 my-0.5 w-full">
              <div className="flex-1 h-px bg-[#E9E9E6]" />
              <span className="text-[10px] font-black text-[#9A9A94] uppercase tracking-wider">OR</span>
              <div className="flex-1 h-px bg-[#E9E9E6]" />
            </div>

            <div className="flex items-center gap-3 w-full">
              <a 
                href={GOOGLE_OAUTH_URL} 
                className="flex-1 flex items-center justify-center h-12 rounded-full bg-white border border-[#E9E9E6] hover:bg-[#FBFBFA] shadow-xs active:scale-[0.98] transition-all"
              >
                <GoogleIcon />
              </a>
              <button 
                type="button"
                onClick={() => finishOnboarding('/login')}
                className="flex-1 flex items-center justify-center h-12 rounded-full bg-white border border-[#E9E9E6] hover:bg-[#FBFBFA] shadow-xs active:scale-[0.98] transition-all"
              >
                <AppleIcon />
              </button>
            </div>
          </div>
        )}

        {/* Account Footer Status */}
        <div className="text-center text-xs font-semibold">
          <span className="text-[#A3A29C]">Already have an account? </span>
          <button 
            type="button"
            onClick={() => finishOnboarding('/login')}
            className="text-[#FF5A36] font-bold hover:underline"
          >
            Log in
          </button>
        </div>

      </footer>

    </main>
  );
}

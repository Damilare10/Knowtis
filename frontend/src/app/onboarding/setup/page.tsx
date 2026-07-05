'use client';

import Link from 'next/link';
import { useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import { useAppStore } from '@/lib/store';
import { GOOGLE_OAUTH_URL } from '@/lib/api';
import {
  ArrowRight, CheckCircle2, Link2, Sparkles, ShieldCheck, ArrowLeft,
} from 'lucide-react';

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

const STEPS = ['connect', 'link', 'done'] as const;
type Step = typeof STEPS[number];

export default function SetupPage() {
  const router = useRouter();
  const { joinGroup, groups, fetchGroups, user, hasHydrated, isAuthenticated } = useAppStore();
  const [userStep, setUserStep] = useState<Step | null>(null);
  const [inviteLink, setInviteLink] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [feedback, setFeedback] = useState<{ type: 'error' | 'success'; text: string } | null>(null);

  // Resolve the active step: user-driven transitions take precedence, otherwise
  // derive from auth state so we never call setState inside an effect.
  const step: Step = useMemo(() => {
    if (userStep) return userStep;
    if (hasHydrated && isAuthenticated && groups.length > 0) return 'done';
    if (hasHydrated && isAuthenticated) return 'link';
    return 'connect';
  }, [userStep, hasHydrated, isAuthenticated, groups.length]);

  // Redirect unauthenticated users once the session has hydrated.
  useEffect(() => {
    if (hasHydrated && !isAuthenticated) {
      router.replace('/login');
    }
  }, [hasHydrated, isAuthenticated, router]);

  useEffect(() => {
    if (isAuthenticated) fetchGroups();
  }, [isAuthenticated, fetchGroups]);

  const handleLink = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inviteLink.trim()) return;
    setSubmitting(true);
    setFeedback(null);
    const ok = await joinGroup(inviteLink);
    setSubmitting(false);
    if (ok) {
      setFeedback({ type: 'success', text: 'Invite received. Knowtis will connect to the chat shortly.' });
      setInviteLink('');
      setTimeout(() => setUserStep('done'), 1400);
    } else {
      setFeedback({ type: 'error', text: 'Could not link that invite. Check the link and try again.' });
    }
  };

  const firstName = (user?.full_name || 'there').split(' ')[0];

  return (
    <main className="relative flex min-h-dvh flex-col items-center bg-[#FBFBFA] overflow-hidden">
      {/* Soft pastel backdrop */}
      <motion.div
        className="pointer-events-none absolute inset-x-0 top-0 h-[55dvh] w-full [mask-image:linear-gradient(to_bottom,black_55%,transparent_100%)]"
        animate={{ backgroundColor: step === 'done' ? '#C5EBE1' : '#FAD7CD' }}
        transition={{ duration: 0.6 }}
      />

      {/* Logo */}
      <div className="relative z-10 pt-7 text-center">
        <Link href="/dashboard" className="inline-flex items-baseline gap-1 text-[18px] font-extrabold tracking-[-0.05em] lowercase">
          <span>know</span>
          <span className="text-[#FF5A36]">tis</span>
        </Link>
      </div>

      <div className="relative z-10 flex w-full max-w-[420px] flex-1 flex-col px-5 pt-8 pb-7">
        <div className="flex-1 flex flex-col">

          {/* Step indicator */}
          <div className="mb-8 flex items-center justify-center gap-2">
            {STEPS.map((s, i) => {
              const idx = STEPS.indexOf(step);
              const active = i <= idx;
              return (
                <div
                  key={s}
                  className={`h-1.5 rounded-full transition-all duration-300 ${active ? 'w-6 bg-[#171717]' : 'w-1.5 bg-[#171717]/15'}`}
                />
              );
            })}
          </div>

          <AnimatePresence mode="wait">
            {/* STEP 1 — Connect account (only shown if not yet authed) */}
            {!isAuthenticated && step === 'connect' && (
              <motion.div
                key="connect"
                initial={{ opacity: 0, x: 30 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -30 }}
                transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
                className="flex flex-col items-center text-center"
              >
                <div className="mb-6 flex h-20 w-20 items-center justify-center rounded-[28px] bg-white shadow-[0_24px_48px_rgba(0,0,0,0.08),inset_0_8px_16px_rgba(255,255,255,0.8)]">
                  <Sparkles className="h-9 w-9 text-[#FF5A36]" strokeWidth={2.2} />
                </div>
                <h1 className="text-[30px] font-black leading-[1.05] tracking-[-0.04em] text-[#171717]">
                  Let&apos;s set up <span className="text-[#FF5A36]">Knowtis</span>
                </h1>
                <p className="mt-3 max-w-[300px] text-[15px] font-medium leading-relaxed text-[#686862]">
                  Sign in or create an account to start filtering your class chats into clean deadlines.
                </p>

                <div className="mt-8 flex w-full flex-col gap-3">
                  <a href={GOOGLE_OAUTH_URL} className="flex h-[52px] w-full items-center justify-center gap-2.5 rounded-full border border-[#E9E9E6] bg-white text-[15px] font-bold text-[#171717] shadow-sm transition-transform active:scale-[0.98]">
                    <GoogleIcon />
                    Continue with Google
                  </a>
                  <Link href="/register" className="flex h-[52px] w-full items-center justify-center gap-2 rounded-full bg-[#171717] text-[15px] font-bold text-white shadow-[0_12px_24px_rgba(30,30,30,0.2)] transition-transform active:scale-[0.98]">
                    Sign up with email <ArrowRight className="w-4 h-4" />
                  </Link>
                  <Link href="/login" className="flex h-[52px] w-full items-center justify-center gap-2 rounded-full border border-[#E9E9E6] bg-white text-[15px] font-bold text-[#171717] shadow-sm transition-transform active:scale-[0.98]">
                    I already have an account
                  </Link>
                </div>
              </motion.div>
            )}

            {/* STEP 2 — Link first class chat */}
            {isAuthenticated && step === 'link' && (
              <motion.div
                key="link"
                initial={{ opacity: 0, x: 30 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -30 }}
                transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
                className="flex flex-col items-center text-center"
              >
                <div className="mb-6 flex h-20 w-20 items-center justify-center rounded-[28px] bg-white shadow-[0_24px_48px_rgba(0,0,0,0.08),inset_0_8px_16px_rgba(255,255,255,0.8)]">
                  <Link2 className="h-9 w-9 text-[#4285F4]" strokeWidth={2.2} />
                </div>
                <h1 className="text-[30px] font-black leading-[1.05] tracking-[-0.04em] text-[#171717]">
                  Link your first <span className="text-[#FF5A36]">class chat</span>
                </h1>
                <p className="mt-3 max-w-[320px] text-[15px] font-medium leading-relaxed text-[#686862]">
                  Hi {firstName}. Paste a WhatsApp group invite link and Knowtis starts surfacing deadlines automatically.
                </p>

                <form onSubmit={handleLink} className="mt-8 w-full space-y-3 text-left">
                  <label htmlFor="invite-link" className="block pl-1 text-[12px] font-bold text-[#686862]">
                    WhatsApp invite link
                  </label>
                  <input
                    id="invite-link"
                    type="text"
                    required
                    placeholder="https://chat.whatsapp.com/..."
                    value={inviteLink}
                    onChange={(e) => setInviteLink(e.target.value)}
                    className="w-full rounded-[20px] border border-[#E9E9E6] bg-[#FBFBFA] py-3.5 px-4 text-sm font-semibold text-[#171717] outline-none transition-all placeholder:text-[#B6B5AE] placeholder:font-normal focus:border-[#FFB29F] focus:bg-white focus:ring-4 focus:ring-[#FF5A36]/10"
                  />

                  <AnimatePresence>
                    {feedback && (
                      <motion.div
                        initial={{ opacity: 0, y: -4 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0 }}
                        className={`rounded-[16px] border p-3 text-xs font-semibold ${
                          feedback.type === 'error'
                            ? 'border-[#FFD8CD] bg-[#FFF0EB] text-[#C83C21]'
                            : 'border-[#CFEFDD] bg-[#EAF8F0] text-[#14794F]'
                        }`}
                      >
                        {feedback.text}
                      </motion.div>
                    )}
                  </AnimatePresence>

                  <button
                    type="submit"
                    disabled={submitting}
                    className="flex h-[52px] w-full items-center justify-center gap-2 rounded-full bg-[#171717] text-[15px] font-bold text-white shadow-[0_12px_24px_rgba(30,30,30,0.2)] transition-transform active:scale-[0.98] disabled:opacity-60"
                  >
                    {submitting ? <span className="skeleton-soft block h-3 w-24 rounded-full" /> : <>Link chat <ArrowRight className="w-4 h-4" /></>}
                  </button>
                </form>

                <div className="mt-4 flex items-start gap-2.5 rounded-[18px] bg-white/70 p-3.5 text-left backdrop-blur-md">
                  <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-[#32B87B]" />
                  <p className="text-[11px] font-medium leading-relaxed text-[#686862]">
                    Knowtis only reads school-related updates — never private messages or media you don&apos;t tag. You can unlink anytime.
                  </p>
                </div>

                <button
                  onClick={() => setUserStep('done')}
                  className="mt-5 text-[12px] font-bold uppercase tracking-wider text-[#9A9A94] hover:text-[#171717] transition-colors"
                >
                  Skip for now
                </button>
              </motion.div>
            )}

            {/* STEP 3 — Done */}
            {step === 'done' && (
              <motion.div
                key="done"
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
                className="flex flex-col items-center text-center"
              >
                <motion.div
                  initial={{ scale: 0 }}
                  animate={{ scale: 1 }}
                  transition={{ delay: 0.15, type: 'spring', stiffness: 200, damping: 14 }}
                  className="mb-6 flex h-20 w-20 items-center justify-center rounded-full bg-[#32B87B] text-white shadow-[0_20px_44px_rgba(50,184,123,0.3),inset_0_6px_10px_rgba(255,255,255,0.3)]"
                >
                  <CheckCircle2 className="h-10 w-10" strokeWidth={2.4} />
                </motion.div>
                <h1 className="text-[30px] font-black leading-[1.05] tracking-[-0.04em] text-[#171717]">
                  You&apos;re all set, {firstName}
                </h1>
                <p className="mt-3 max-w-[320px] text-[15px] font-medium leading-relaxed text-[#686862]">
                  {groups.length > 0
                    ? 'Knowtis is now watching your class chat for deadlines, alerts, and schedule changes.'
                    : 'You can link a class chat anytime from the Groups page. Your dashboard is ready.'}
                </p>

                <Link
                  href="/dashboard"
                  className="mt-8 flex h-[52px] w-full items-center justify-center gap-2 rounded-full bg-[#171717] text-[15px] font-bold text-white shadow-[0_12px_24px_rgba(30,30,30,0.2)] transition-transform active:scale-[0.98]"
                >
                  Go to dashboard <ArrowRight className="w-4 h-4" />
                </Link>

                {groups.length === 0 && (
                  <button
                    onClick={() => setUserStep('link')}
                    className="mt-3 flex items-center gap-1.5 text-[13px] font-bold text-[#FF5A36] hover:underline"
                  >
                    <ArrowLeft className="w-3.5 h-3.5" /> Link a chat first
                  </button>
                )}
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </main>
  );
}
